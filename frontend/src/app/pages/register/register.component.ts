import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './register.component.html',
  styleUrl: './register.component.scss',
})
export class RegisterComponent {
  email = '';
  password = '';
  error = '';
  loading = false;

  constructor(private auth: AuthService, private router: Router) {}

  onSubmit() {
    if (this.password.length < 6) {
      this.error = 'Password must be at least 6 characters';
      return;
    }
    this.loading = true;
    this.error = '';
    this.auth.register(this.email, this.password).subscribe({
      next: () => {
        this.auth.login(this.email, this.password).subscribe({
          next: () => this.router.navigate(['/dashboard']),
        });
      },
      error: (err) => {
        this.error = err.error?.detail || 'Registration failed';
        this.loading = false;
      },
    });
  }
}