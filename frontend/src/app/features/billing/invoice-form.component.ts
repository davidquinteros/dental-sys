import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { BillingService, PatientService } from '../../core/services/api.service';
import { Patient } from '../../core/models';

@Component({
  selector: 'app-invoice-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterLink],
  templateUrl: './invoice-form.component.html',
  styleUrl: './invoice-form.component.css',
})
export class InvoiceFormComponent implements OnInit {
  form: FormGroup;
  saving = signal(false);
  errorMsg = signal('');
  selectedPatient = signal<Patient | null>(null);
  patientResults = signal<Patient[]>([]);
  patientSearch = '';
  private searchTimeout: any;

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private billingService: BillingService,
    private patientService: PatientService,
  ) {
    this.form = this.fb.group({
      appointment_id: [''],
      due_date: [''],
      discount: [0],
      notes: [''],
      items: this.fb.array([this.newItem()]),
    });
  }

  get itemsArray(): FormArray { return this.form.get('items') as FormArray; }

  newItem(): FormGroup {
    return this.fb.group({
      description: ['', Validators.required],
      quantity: [1, [Validators.required, Validators.min(1)]],
      unit_price: [0, [Validators.required, Validators.min(0)]],
    });
  }

  ngOnInit(): void {
    const patientId = this.route.snapshot.queryParamMap.get('patient_id');
    if (patientId) {
      this.patientService.getById(+patientId).subscribe(res => this.selectedPatient.set(res.patient));
    }
    const appointmentId = this.route.snapshot.queryParamMap.get('appointment_id');
    if (appointmentId) this.form.patchValue({ appointment_id: +appointmentId });
  }

  addItem(): void { this.itemsArray.push(this.newItem()); }
  removeItem(i: number): void { if (this.itemsArray.length > 1) this.itemsArray.removeAt(i); }

  recalcItem(i: number): void { /* reactive, computed by getters */ }

  itemTotal(i: number): number {
    const item = this.itemsArray.at(i).value;
    return (item.quantity || 0) * (item.unit_price || 0);
  }

  subtotal(): number { return this.itemsArray.controls.reduce((s, _, i) => s + this.itemTotal(i), 0); }
  grandTotal(): number { return Math.max(0, this.subtotal() - (this.form.get('discount')?.value || 0)); }

  onSearch(): void {
    clearTimeout(this.searchTimeout);
    if (!this.patientSearch || this.patientSearch.length < 2) { this.patientResults.set([]); return; }
    this.searchTimeout = setTimeout(() => {
      this.patientService.getAll({ search: this.patientSearch, per_page: 8 }).subscribe(
        res => this.patientResults.set(res.patients)
      );
    }, 300);
  }

  selectPatient(p: Patient): void { this.selectedPatient.set(p); this.patientResults.set([]); this.patientSearch = ''; }
  clearPatient(): void { this.selectedPatient.set(null); }

  formatMoney(val: number): string {
    return new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val || 0);
  }

  onSubmit(): void {
    if (!this.selectedPatient()) { this.errorMsg.set('Seleccione un paciente'); return; }
    this.saving.set(true);
    const val = this.form.value;
    const items = val.items.map((item: any) => ({
      ...item,
      quantity: +item.quantity,
      unit_price: +item.unit_price,
    }));
    const payload: any = {
      patient_id: this.selectedPatient()!.id,
      discount: +val.discount || 0,
      notes: val.notes || null,
      items,
    };
    if (val.appointment_id) payload.appointment_id = +val.appointment_id;
    if (val.due_date) payload.due_date = val.due_date;

    this.billingService.createInvoice(payload).subscribe({
      next: res => this.router.navigate(['/billing/invoices', res.invoice.id]),
      error: err => { this.errorMsg.set(err.error?.error || 'Error al crear la factura'); this.saving.set(false); },
    });
  }
}
