import { Component, OnInit, signal, computed, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import {
  CalendarModule, CalendarView, CalendarEvent, DateAdapter,
  CalendarUtils, CalendarA11y, CalendarDateFormatter, CalendarEventTitleFormatter,
} from 'angular-calendar';
import { adapterFactory } from 'angular-calendar/date-adapters/date-fns';
import {
  startOfDay, endOfDay, startOfWeek, endOfWeek, startOfMonth, endOfMonth,
  addDays, addWeeks, addMonths, subDays, subWeeks, subMonths,
} from 'date-fns';
import { AppointmentService, UserService } from '../../core/services/api.service';
import { Appointment, User } from '../../core/models';

const DOCTOR_COLORS: { primary: string; secondary: string }[] = [
  { primary: '#2b6cb0', secondary: '#ebf8ff' },
  { primary: '#319795', secondary: '#e6fffa' },
  { primary: '#805ad5', secondary: '#faf5ff' },
  { primary: '#dd6b20', secondary: '#fffaf0' },
  { primary: '#38a169', secondary: '#f0fff4' },
  { primary: '#d53f8c', secondary: '#fff5f7' },
  { primary: '#3182ce', secondary: '#ebf8ff' },
  { primary: '#718096', secondary: '#f7fafc' },
  { primary: '#b7791f', secondary: '#fffff0' },
  { primary: '#e53e3e', secondary: '#fff5f5' },
];

/** Converts a Date to a naive ISO string (no timezone), matching how `scheduled_at` is stored. */
function toLocalIso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

@Component({
  selector: 'app-calendar',
  standalone: true,
  imports: [CommonModule, CalendarModule, RouterLink],
  providers: [
    { provide: DateAdapter, useFactory: adapterFactory },
    CalendarUtils,
    CalendarA11y,
    CalendarDateFormatter,
    CalendarEventTitleFormatter,
  ],
  templateUrl: './calendar.component.html',
  styleUrl: './calendar.component.css',
})
export class CalendarComponent implements OnInit {
  /** When true: hides doctor legend, disables navigation to new-appointment page,
   *  and emits dateSelected instead of routing on slot click.
   *  Setter falls back to the default on `undefined`/`null` because this component is also
   *  routed directly (the `/calendar` page) — Angular's `withComponentInputBinding` calls
   *  `setInput()` with `undefined` for every declared @Input with no matching route
   *  data/param/queryParam, which would otherwise clobber the field initializer below. */
  private _embedded = false;
  @Input() set embedded(value: boolean) { this._embedded = value ?? false; }
  get embedded(): boolean { return this._embedded; }

  /** When false, hides the internal page title/wrapper — for when a host page (e.g. the dashboard) already provides its own card chrome. Ignored when embedded. Same undefined-fallback reason as `embedded` above. */
  private _showHeader = true;
  @Input() set showHeader(value: boolean) { this._showHeader = value ?? true; }
  get showHeader(): boolean { return this._showHeader; }

  @Output() dateSelected = new EventEmitter<string>();

  /** Slot to highlight on the calendar as "currently being registered" (e.g. the appointment form's pending date/duration). */
  @Input() set previewSlot(value: { start: Date; end: Date } | null) {
    this.previewSlotSig.set(value);
  }
  private previewSlotSig = signal<{ start: Date; end: Date } | null>(null);

  CalendarView = CalendarView;
  view = signal<CalendarView>(CalendarView.Week);
  viewDate = signal(new Date());
  events = signal<CalendarEvent<Appointment>[]>([]);
  doctors = signal<User[]>([]);
  selectedDoctorIds = signal<Set<number>>(new Set());
  loading = signal(false);

  doctorColorMap = computed(() => {
    const map = new Map<number, { primary: string; secondary: string }>();
    this.doctors().forEach((d, i) => map.set(d.id, DOCTOR_COLORS[i % DOCTOR_COLORS.length]));
    return map;
  });

  filteredEvents = computed(() => {
    const selected = this.selectedDoctorIds();
    const base = this.events().filter(e => selected.has(e.meta!.doctor_id));
    const preview = this.previewSlotSig();
    if (!preview) return base;
    return [...base, {
      start: preview.start,
      end: preview.end,
      title: 'Horario seleccionado',
      color: { primary: '#38a169', secondary: '#c6f6d5' },
      cssClass: 'appt-preview',
    } as CalendarEvent<Appointment>];
  });

  rangeLabel = computed(() => {
    const d = this.viewDate();
    switch (this.view()) {
      case CalendarView.Month:
        return d.toLocaleDateString('es-BO', { month: 'long', year: 'numeric' });
      case CalendarView.Day:
        return d.toLocaleDateString('es-BO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
      default: {
        const start = startOfWeek(d, { weekStartsOn: 1 });
        const end = endOfWeek(d, { weekStartsOn: 1 });
        const fmt = (date: Date) => date.toLocaleDateString('es-BO', { day: 'numeric', month: 'short' });
        return `${fmt(start)} - ${fmt(end)}, ${end.getFullYear()}`;
      }
    }
  });

  constructor(
    private apptService: AppointmentService,
    private userService: UserService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    if (this.embedded) this.view.set(CalendarView.Day);
    this.userService.getDoctors().subscribe(res => {
      this.doctors.set(res.doctors);
      this.selectedDoctorIds.set(new Set(res.doctors.map(d => d.id)));
      this.loadEvents();
    });
  }

  toggleDoctor(id: number): void {
    this.selectedDoctorIds.update(set => {
      const next = new Set(set);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  setView(view: CalendarView): void {
    this.view.set(view);
    this.loadEvents();
  }

  goToday(): void {
    this.viewDate.set(new Date());
    this.loadEvents();
  }

  previous(): void { this.navigate(-1); }
  next(): void { this.navigate(1); }

  private navigate(direction: number): void {
    const d = this.viewDate();
    let newDate: Date;
    switch (this.view()) {
      case CalendarView.Month:
        newDate = direction > 0 ? addMonths(d, 1) : subMonths(d, 1);
        break;
      case CalendarView.Week:
        newDate = direction > 0 ? addWeeks(d, 1) : subWeeks(d, 1);
        break;
      default:
        newDate = direction > 0 ? addDays(d, 1) : subDays(d, 1);
    }
    this.viewDate.set(newDate);
    this.loadEvents();
  }

  loadEvents(): void {
    const d = this.viewDate();
    let start: Date;
    let end: Date;
    switch (this.view()) {
      case CalendarView.Month:
        start = startOfMonth(d); end = endOfMonth(d);
        break;
      case CalendarView.Week:
        start = startOfWeek(d, { weekStartsOn: 1 }); end = endOfWeek(d, { weekStartsOn: 1 });
        break;
      default:
        start = startOfDay(d); end = endOfDay(d);
    }

    this.loading.set(true);
    this.apptService.getAll({
      date_from: toLocalIso(start),
      date_to: toLocalIso(end),
      all: true,
      per_page: 500,
    }).subscribe({
      next: res => {
        const colorMap = this.doctorColorMap();
        const events: CalendarEvent<Appointment>[] = (res.appointments as Appointment[]).map(a => {
          const eventStart = new Date(a.scheduled_at);
          const eventEnd = new Date(eventStart.getTime() + a.duration_minutes * 60000);
          const inactive = a.status === 'cancelled' || a.status === 'no_show';
          return {
            id: a.id,
            start: eventStart,
            end: eventEnd,
            title: `${a.patient_name} · Dr. ${a.doctor_name}${a.consultorio_name ? ' · ' + a.consultorio_name : ''}`,
            color: colorMap.get(a.doctor_id) ?? DOCTOR_COLORS[0],
            cssClass: inactive ? 'appt-inactive' : undefined,
            meta: a,
          };
        });
        this.events.set(events);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  onEventClicked({ event }: { event: CalendarEvent<Appointment> }): void {
    if (!this.embedded) {
      this.router.navigate(['/appointments', event.meta!.id, 'edit']);
    }
  }

  onHourSegmentClicked({ date }: { date: Date }): void {
    if (this.embedded) {
      this.dateSelected.emit(toLocalIso(date));
    } else {
      this.router.navigate(['/appointments/new'], { queryParams: { date: toLocalIso(date) } });
    }
  }

  onDayClicked({ day }: { day: { date: Date } }): void {
    const d = new Date(day.date);
    d.setHours(9, 0, 0, 0);
    if (this.embedded) {
      this.dateSelected.emit(toLocalIso(d));
    } else {
      this.router.navigate(['/appointments/new'], { queryParams: { date: toLocalIso(d) } });
    }
  }
}
