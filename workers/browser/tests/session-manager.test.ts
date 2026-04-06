import assert from "node:assert/strict";

import type { Cookie } from "playwright";

import { AuthProfileApiClient } from "../src/api-client.js";
import type { SessionRequest } from "../src/contracts.js";
import {
  type BrowserContextLike,
  type BrowserLike,
  type BrowserLauncherLike,
  type PageLike,
  SessionManager,
} from "../src/session-manager.js";

function run(name: string, fn: () => Promise<void> | void): Promise<void> {
  return Promise.resolve(fn()).then(() => {
    console.log(`ok - ${name}`);
  });
}

class MockLocator {
  constructor(private readonly visible: boolean) {}

  async isVisible(): Promise<boolean> {
    return this.visible;
  }
}

class MockPage implements PageLike {
  public readonly visits: string[] = [];
  public readonly fills: Array<{ selector: string; value: string }> = [];
  public readonly clicks: string[] = [];

  constructor(
    private readonly locatorVisibility: Record<string, boolean>,
    private currentUrl: string,
    private readonly html: string,
  ) {}

  async goto(url: string): Promise<void> {
    this.currentUrl = url;
    this.visits.push(url);
  }

  async fill(selector: string, value: string): Promise<void> {
    this.fills.push({ selector, value });
  }

  async click(selector: string): Promise<void> {
    this.clicks.push(selector);
  }

  locator(selector: string): MockLocator {
    return new MockLocator(Boolean(this.locatorVisibility[selector]));
  }

  url(): string {
    return this.currentUrl;
  }

  async content(): Promise<string> {
    return this.html;
  }
}

class MockContext implements BrowserContextLike {
  public readonly addedCookies: Cookie[] = [];
  public readonly storageStatePaths: string[] = [];

  constructor(private readonly page: MockPage) {}

  async newPage(): Promise<MockPage> {
    return this.page;
  }

  async addCookies(cookies: Cookie[]): Promise<void> {
    this.addedCookies.push(...cookies);
  }

  async storageState(options?: { path?: string }): Promise<object> {
    if (options?.path) {
      this.storageStatePaths.push(options.path);
    }
    return {};
  }

  async close(): Promise<void> {
    return;
  }
}

class MockBrowser implements BrowserLike {
  public readonly newContextCalls: Array<{ storageState?: string } | undefined> = [];

  constructor(private readonly context: MockContext) {}

  async newContext(options?: { storageState?: string }): Promise<MockContext> {
    this.newContextCalls.push(options);
    return this.context;
  }

  async close(): Promise<void> {
    return;
  }
}

class MockLauncher implements BrowserLauncherLike {
  constructor(private readonly browser: MockBrowser) {}

  async launch(): Promise<MockBrowser> {
    return this.browser;
  }
}

await run("SessionManager handles username/password login and validates access", async () => {
  const page = new MockPage({ "[data-authenticated='true']": true }, "https://example.com/course/1", "<div>ready</div>");
  const context = new MockContext(page);
  const browser = new MockBrowser(context);
  const sessionManager = new SessionManager(new MockLauncher(browser));

  const request: SessionRequest = {
    authRole: "learner",
    courseUrl: "https://example.com/course/1",
    loginFlow: {
      username: "learner@example.com",
      password: "secret",
      selectors: {
        loginUrl: "https://example.com/login",
        usernameSelector: "#username",
        passwordSelector: "#password",
        submitSelector: "button[type=submit]",
      },
    },
    validation: {
      authenticatedSelector: "[data-authenticated='true']",
    },
    persistSessionStatePath: "var/evidence/session-state.json",
  };

  const result = await sessionManager.establishSession(request);

  assert.equal(result.validationStatus, "validated");
  assert.equal(result.authenticated, true);
  assert.equal(result.authContext.role, "learner");
  assert.equal(result.authContext.login_method, "username_password");
  assert.equal(result.sessionStatePath, "var/evidence/session-state.json");
  assert.deepEqual(page.visits, ["https://example.com/login", "https://example.com/course/1"]);
  assert.deepEqual(page.fills, [
    { selector: "#username", value: "learner@example.com" },
    { selector: "#password", value: "secret" },
  ]);
  assert.deepEqual(page.clicks, ["button[type=submit]"]);
  assert.deepEqual(context.storageStatePaths, ["var/evidence/session-state.json"]);
});

await run("SessionManager supports manual cookie fallback and logs CAPTCHA bypass", async () => {
  const cookies: Cookie[] = [
    {
      name: "sessionid",
      value: "abc123",
      domain: "example.com",
      path: "/",
      expires: -1,
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
    },
  ];
  const page = new MockPage({}, "https://example.com/course/2", "<div>Instructor Dashboard</div>");
  const context = new MockContext(page);
  const browser = new MockBrowser(context);
  const sessionManager = new SessionManager(new MockLauncher(browser));

  const result = await sessionManager.establishSession({
    authRole: "instructor",
    courseUrl: "https://example.com/course/2",
    manualSession: {
      cookies,
      captchaBypassedManually: true,
    },
    validation: {
      authenticatedTextPattern: "Instructor Dashboard",
    },
  });

  assert.equal(result.validationStatus, "validated");
  assert.equal(result.authContext.login_method, "manual_cookie_injection");
  assert.equal(result.authContext.captcha_bypassed_manually, true);
  assert.equal(result.sessionStatePath, "encrypted-blob-placeholder:manual-cookie-session");
  assert.equal(context.addedCookies.length, 1);
  assert.ok(result.authContext.notes.includes("CAPTCHA was bypassed manually via imported session."));
});

await run("SessionManager returns failed validation when no signal matches", async () => {
  const page = new MockPage({}, "https://example.com/guest", "<div>guest</div>");
  const context = new MockContext(page);
  const browser = new MockBrowser(context);
  const sessionManager = new SessionManager(new MockLauncher(browser));

  const result = await sessionManager.establishSession({
    authRole: "admin",
    courseUrl: "https://example.com/admin",
    manualSession: {
      storageStatePath: "var/evidence/admin-state.json",
    },
    validation: {
      authenticatedSelector: "[data-authenticated='true']",
      authenticatedUrlPattern: "/dashboard$",
    },
  });

  assert.equal(result.validationStatus, "failed");
  assert.equal(result.sessionStatePath, "var/evidence/admin-state.json");
  assert.deepEqual(browser.newContextCalls, [{ storageState: "var/evidence/admin-state.json" }]);
});

await run("AuthProfileApiClient maps session results into API payloads", async () => {
  const requests: Array<{ input: string; init?: { method?: string; headers?: Record<string, string>; body?: string } }> =
    [];
  const client = new AuthProfileApiClient("http://127.0.0.1:8000", async (input, init) => {
    requests.push({ input, init });
    return {
      ok: true,
      status: 201,
      async json() {
        return {
          auth_profile_id: "auth-1",
          run_id: "run-1",
          auth_context: { role: "learner" },
          session_state_path: "var/evidence/session-state.json",
          validation_status: "validated",
          created_at: "2026-04-06T00:00:00Z",
        };
      },
      async text() {
        return "";
      },
    };
  });

  const payload = client.buildCreateRequest("run-1", {
    authContext: {
      role: "learner",
      login_method: "username_password",
      captcha_bypassed_manually: false,
      notes: [],
    },
    sessionStatePath: "var/evidence/session-state.json",
    validationStatus: "validated",
    authenticated: true,
  });

  const response = await client.createAuthProfile(payload);

  assert.equal(response.auth_profile_id, "auth-1");
  assert.equal(requests[0]?.input, "http://127.0.0.1:8000/auth-profiles");
  assert.equal(requests[0]?.init?.method, "POST");
  assert.deepEqual(JSON.parse(requests[0]?.init?.body ?? "{}"), payload);
});
