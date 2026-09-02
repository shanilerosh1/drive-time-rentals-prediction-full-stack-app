import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../core/services/auth.service';
import { DamageClassService } from '../core/services/damage-class.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="shell">
      <aside class="sidebar" [class.open]="menuOpen()">
        <div class="brand">
          <div class="mark" aria-hidden="true">DT</div>
          <div>
            <div class="name">DriveTime</div>
            <div class="sub">Damage Inspection</div>
          </div>
        </div>

        <nav>
          <a
            *ngFor="let item of nav"
            [routerLink]="item.link"
            routerLinkActive="active"
            [routerLinkActiveOptions]="{ exact: item.exact }"
            (click)="menuOpen.set(false)"
          >
            <span class="icon" aria-hidden="true">{{ item.icon }}</span>
            {{ item.label }}
          </a>
        </nav>

        <div class="sidebar-foot">
          <a routerLink="/inspections/new" class="btn btn-primary btn-block" (click)="menuOpen.set(false)">
            + New inspection
          </a>
        </div>
      </aside>

      <div class="main">
        <header class="topbar">
          <button class="btn btn-ghost menu-toggle" (click)="menuOpen.set(!menuOpen())" aria-label="Toggle navigation">
            ☰
          </button>
          <div class="spacer"></div>
          <div class="user" *ngIf="auth.user() as user">
            <div class="who">
              <div class="uname">{{ user.full_name }}</div>
              <div class="urole">{{ user.role === 'admin' ? 'Administrator' : 'Inspector' }}</div>
            </div>
            <div class="avatar" [title]="user.email">{{ initials(user.full_name) }}</div>
            <button class="btn btn-sm" (click)="auth.logout()">Sign out</button>
          </div>
        </header>

        <main>
          <router-outlet />
        </main>
      </div>

      <div class="scrim" *ngIf="menuOpen()" (click)="menuOpen.set(false)"></div>
    </div>
  `,
  styles: [
    `
      .shell { display: flex; min-height: 100vh; }

      .sidebar {
        width: 232px;
        flex: none;
        background: var(--brand-900);
        color: #cdd8e8;
        display: flex;
        flex-direction: column;
        position: sticky;
        top: 0;
        height: 100vh;
      }
      .brand {
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 18px 18px 20px;
      }
      .mark {
        width: 34px;
        height: 34px;
        border-radius: 9px;
        background: var(--brand-500);
        color: #fff;
        display: grid;
        place-items: center;
        font-weight: 750;
        font-size: 0.8125rem;
        letter-spacing: 0.02em;
      }
      .name { color: #fff; font-weight: 650; font-size: 0.9375rem; line-height: 1.2; }
      .sub { font-size: 0.6875rem; color: #8fa5c2; }

      nav { display: flex; flex-direction: column; gap: 2px; padding: 8px 10px; flex: 1; }
      nav a {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 9px 11px;
        border-radius: var(--radius-sm);
        color: #b9c8dd;
        font-size: 0.8125rem;
        font-weight: 550;
        text-decoration: none;
        transition: background 0.14s ease, color 0.14s ease;
      }
      nav a:hover { background: rgba(255, 255, 255, 0.07); color: #fff; text-decoration: none; }
      nav a.active { background: var(--brand-700); color: #fff; }
      .icon { width: 18px; text-align: center; font-size: 0.9375rem; }

      .sidebar-foot { padding: 12px; border-top: 1px solid rgba(255, 255, 255, 0.09); }
      .sidebar-foot .btn { text-decoration: none; }

      .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
      .topbar {
        display: flex;
        align-items: center;
        gap: 12px;
        height: 56px;
        padding: 0 20px;
        background: var(--surface);
        border-bottom: 1px solid var(--border);
        position: sticky;
        top: 0;
        z-index: 20;
      }
      .menu-toggle { display: none; font-size: 1.05rem; }

      .user { display: flex; align-items: center; gap: 10px; }
      .who { text-align: right; line-height: 1.25; }
      .uname { font-size: 0.8125rem; font-weight: 600; }
      .urole { font-size: 0.6875rem; color: var(--ink-500); }
      .avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--brand-050);
        color: var(--brand-700);
        display: grid;
        place-items: center;
        font-size: 0.75rem;
        font-weight: 700;
      }

      main { flex: 1; }
      .scrim { display: none; }

      @media (max-width: 860px) {
        .sidebar {
          position: fixed;
          z-index: 40;
          transform: translateX(-100%);
          transition: transform 0.2s ease;
        }
        .sidebar.open { transform: translateX(0); }
        .menu-toggle { display: inline-flex; }
        .scrim {
          display: block;
          position: fixed;
          inset: 0;
          background: rgba(15, 20, 32, 0.45);
          z-index: 30;
        }
        .who { display: none; }
      }
    `,
  ],
})
export class ShellComponent {
  readonly auth = inject(AuthService);
  private readonly damageClasses = inject(DamageClassService);

  readonly menuOpen = signal(false);

  readonly nav = [
    { link: '/dashboard', label: 'Dashboard', icon: '▤', exact: true },
    { link: '/inspections', label: 'Inspections', icon: '☑', exact: false },
    { link: '/vehicles', label: 'Fleet', icon: '⛃', exact: false },
    { link: '/comparison', label: 'Pre / post', icon: '⇄', exact: true },
    { link: '/model', label: 'Model', icon: '◈', exact: true },
  ];

  constructor() {
    // Reaching the shell means an authenticated session; make sure the
    // taxonomy is loaded even on a deep-link that skipped the root init.
    this.damageClasses.load();
  }

  initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }
}
