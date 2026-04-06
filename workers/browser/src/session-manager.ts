import { chromium, type Browser, type BrowserContext, type BrowserType, type Cookie, type Page } from "playwright";

import type {
  AuthenticatedAccessSignal,
  LoginMethod,
  ManualSessionImport,
  SessionRequest,
  SessionResult,
  ValidationStatus,
} from "./contracts.js";

export interface LocatorLike {
  isVisible(): Promise<boolean>;
}

export interface PageLike {
  goto(url: string): Promise<unknown>;
  fill(selector: string, value: string): Promise<void>;
  click(selector: string): Promise<void>;
  locator(selector: string): LocatorLike;
  url(): string;
  content(): Promise<string>;
}

export interface BrowserContextLike {
  newPage(): Promise<PageLike>;
  addCookies(cookies: Cookie[]): Promise<void>;
  storageState(options?: { path?: string }): Promise<unknown>;
  close(): Promise<void>;
}

export interface BrowserLike {
  newContext(options?: { storageState?: string }): Promise<BrowserContextLike>;
  close(): Promise<void>;
}

export interface BrowserLauncherLike {
  launch(): Promise<BrowserLike>;
}

class PlaywrightBrowserLauncher implements BrowserLauncherLike {
  constructor(
    private readonly browserType: BrowserType<Browser> = chromium,
    private readonly launchOptions: Parameters<BrowserType<Browser>["launch"]>[0] = { headless: true },
  ) {}

  async launch(): Promise<BrowserLike> {
    const browser = await this.browserType.launch(this.launchOptions);
    return browser as unknown as BrowserLike;
  }
}

export class SessionManager {
  constructor(private readonly launcher: BrowserLauncherLike = new PlaywrightBrowserLauncher()) {}

  async establishSession(request: SessionRequest): Promise<SessionResult> {
    const browser = await this.launcher.launch();
    const context = await browser.newContext(this.buildContextOptions(request.manualSession));
    const authContext = this.buildAuthContext(request);

    try {
      if (request.manualSession?.cookies?.length) {
        await context.addCookies(request.manualSession.cookies);
      }

      const page = await context.newPage();

      if (request.loginFlow) {
        await this.performLogin(page, request);
      }

      await page.goto(request.courseUrl);
      const validationStatus = await this.validateAuthenticatedAccess(page, request.validation);
      const sessionStatePath = await this.persistSessionState(context, request, authContext.login_method);

      return {
        authContext,
        sessionStatePath,
        validationStatus,
        authenticated: validationStatus === "validated",
      };
    } finally {
      await context.close();
      await browser.close();
    }
  }

  async validateAuthenticatedAccess(
    page: PageLike | Page,
    validation: AuthenticatedAccessSignal,
  ): Promise<ValidationStatus> {
    const hasSignals =
      Boolean(validation.authenticatedSelector) ||
      Boolean(validation.authenticatedUrlPattern) ||
      Boolean(validation.authenticatedTextPattern);
    if (!hasSignals) {
      return "pending";
    }

    if (validation.authenticatedSelector) {
      const isVisible = await page.locator(validation.authenticatedSelector).isVisible();
      if (isVisible) {
        return "validated";
      }
    }

    if (validation.authenticatedUrlPattern) {
      const pattern = new RegExp(validation.authenticatedUrlPattern, "i");
      if (pattern.test(page.url())) {
        return "validated";
      }
    }

    if (validation.authenticatedTextPattern) {
      const pattern = new RegExp(validation.authenticatedTextPattern, "i");
      if (pattern.test(await page.content())) {
        return "validated";
      }
    }

    return "failed";
  }

  private async performLogin(page: PageLike | Page, request: SessionRequest): Promise<void> {
    if (!request.loginFlow) {
      return;
    }
    const { username, password, selectors } = request.loginFlow;
    await page.goto(selectors.loginUrl);
    await page.fill(selectors.usernameSelector, username);
    await page.fill(selectors.passwordSelector, password);
    await page.click(selectors.submitSelector);
  }

  private buildContextOptions(manualSession?: ManualSessionImport): { storageState?: string } | undefined {
    if (!manualSession?.storageStatePath) {
      return undefined;
    }
    return { storageState: manualSession.storageStatePath };
  }

  private buildAuthContext(request: SessionRequest): SessionResult["authContext"] {
    const loginMethod = this.resolveLoginMethod(request);
    const notes: string[] = [];
    if (request.manualSession?.captchaBypassedManually) {
      notes.push("CAPTCHA was bypassed manually via imported session.");
    }
    if (loginMethod === "manual_cookie_injection" && !request.manualSession?.storageStatePath) {
      notes.push("Manual cookie injection fallback was used.");
    }

    return {
      role: request.authRole,
      login_method: loginMethod,
      captcha_bypassed_manually: Boolean(request.manualSession?.captchaBypassedManually),
      notes,
    };
  }

  private resolveLoginMethod(request: SessionRequest): LoginMethod {
    if (request.loginFlow) {
      return "username_password";
    }
    if (request.manualSession?.storageStatePath) {
      return "manual_storage_state";
    }
    return "manual_cookie_injection";
  }

  private async persistSessionState(
    context: BrowserContextLike,
    request: SessionRequest,
    loginMethod: LoginMethod,
  ): Promise<string | null> {
    if (request.persistSessionStatePath) {
      await context.storageState({ path: request.persistSessionStatePath });
      return request.persistSessionStatePath;
    }
    if (request.manualSession?.storageStatePath) {
      return request.manualSession.storageStatePath;
    }
    if (loginMethod === "manual_cookie_injection") {
      return "encrypted-blob-placeholder:manual-cookie-session";
    }
    return null;
  }
}
