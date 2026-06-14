import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PatientService } from '../../core/services/api.service';
import { Patient } from '../../core/models';

@Component({
  selector: 'app-patients',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './patients-list.component.html',
  styleUrl: './patients-list.component.css',
})
export class PatientsListComponent implements OnInit {
  patients = signal<Patient[]>([]);
  loading = signal(true);
  searchTerm = '';
  total = signal(0);
  currentPage = signal(1);
  totalPages = signal(1);
  private searchTimeout: any;

  constructor(private patientService: PatientService) {}

  ngOnInit(): void { this.loadPatients(); }

  loadPatients(): void {
    this.loading.set(true);
    this.patientService.getAll({ page: this.currentPage(), search: this.searchTerm, per_page: 20 }).subscribe({
      next: res => {
        this.patients.set(res.patients);
        this.total.set(res.total);
        this.totalPages.set(res.pages || 1);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  onSearch(term: string): void {
    clearTimeout(this.searchTimeout);
    this.searchTimeout = setTimeout(() => {
      this.currentPage.set(1);
      this.loadPatients();
    }, 400);
  }

  clearSearch(): void {
    this.searchTerm = '';
    this.currentPage.set(1);
    this.loadPatients();
  }

  goToPage(page: number): void {
    this.currentPage.set(page);
    this.loadPatients();
  }

  pageNumbers(): number[] {
    const total = this.totalPages();
    const current = this.currentPage();
    const pages: number[] = [];
    const start = Math.max(1, current - 2);
    const end = Math.min(total, current + 2);
    for (let i = start; i <= end; i++) pages.push(i);
    return pages;
  }

  initials(p: Patient): string {
    return `${p.first_name[0]}${p.last_name[0]}`.toUpperCase();
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-BO', { day: '2-digit', month: 'short', year: 'numeric' });
  }
}
