import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AuthService } from './core/services/auth.service';
import { DamageClassService } from './core/services/damage-class.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class AppComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly damageClasses = inject(DamageClassService);

  ngOnInit(): void {
    // A stored token may have expired while the tab was closed; confirm it and
    // let the interceptor sign the user out if it is stale.
    if (this.auth.isAuthenticated()) {
      this.auth.refreshProfile().subscribe({ error: () => undefined });
      this.damageClasses.load();
    }
  }
}
