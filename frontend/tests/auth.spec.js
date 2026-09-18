import { test, expect } from "@playwright/test";

const user = {
  id: 7,
  name: "Alex Morgan",
  email: "alex@example.com",
  memory_enabled: false,
  created_at: "2026-09-16T00:00:00Z",
};
const sessionKey = "constraintcanvas.session";

async function mockApi(
  page,
  {
    loginStatus = 200,
    registerStatus = 201,
    meStatus = 200,
    expiresIn = 3600,
  } = {},
) {
  const requests = [];
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    requests.push({
      path,
      method: req.method(),
      body: req.postDataJSON(),
      authorization: req.headers().authorization,
    });
    let status = 404;
    let body = { detail: "Unexpected endpoint: " + path };
    if (path === "/api/auth/login") {
      status = loginStatus;
      body =
        status === 200
          ? {
              access_token: "opaque-test-token",
              token_type: "bearer",
              expires_in: expiresIn,
            }
          : { detail: "Invalid email or password" };
    } else if (path === "/api/auth/me") {
      status = meStatus;
      body =
        status === 200
          ? user
          : { detail: "Invalid authentication credentials" };
    } else if (path === "/api/auth/register") {
      status = registerStatus;
      body =
        status === 201
          ? user
          : status === 409
            ? { detail: "An account with this email already exists" }
            : {
                detail: [
                  {
                    loc: ["body", "email"],
                    msg: "This email address is not accepted",
                    type: "value_error",
                  },
                ],
              };
    }
    await route.fulfill({ status, json: body });
  });
  return requests;
}
async function signIn(page) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("alex@example.com");
  await page.getByLabel("Password", { exact: true }).fill("testing-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
async function fillRegistration(page) {
  await page.goto("/register");
  await page.getByLabel("Full name").fill("Alex Morgan");
  await page.getByLabel("Email address").fill("alex@example.com");
  await page.getByLabel("Password", { exact: true }).fill("testing-password");
  await page.getByLabel("Confirm password").fill("testing-password");
}
test.beforeEach(async ({ page }) => {
  await page.route("https://fonts.googleapis.com/**", (route) => route.abort());
  await page.route("https://fonts.gstatic.com/**", (route) => route.abort());
});
test("login and signup render accessibly without horizontal overflow", async ({
  page,
}, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("login.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "Create an account" }).click();
  await expect(
    page.getByRole("heading", { name: "Create your account" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await page.getByRole("button", { name: "Hide password" }).click();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "type",
    "password",
  );
  await page.screenshot({
    path: testInfo.outputPath("register.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
for (const path of ["/dashboard", "/plans", "/settings"]) {
  test("anonymous route " + path + " redirects to login", async ({ page }) => {
    await page.goto(path);
    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { name: "Welcome back." }),
    ).toBeVisible();
  });
}
test("invalid login presents the API error and keeps the form usable", async ({
  page,
}) => {
  const requests = await mockApi(page, { loginStatus: 401 });
  await signIn(page);
  await expect(page.getByRole("alert")).toContainText(
    "Invalid email or password",
  );
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
  expect(requests[0].body).toEqual({
    email: "alex@example.com",
    password: "testing-password",
  });
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), sessionKey),
  ).toBeNull();
});
test("registration validates locally, registers, and redirects to login", async ({
  page,
}) => {
  const requests = await mockApi(page);
  await fillRegistration(page);
  await page.getByLabel("Confirm password").fill("different");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByText("Your passwords do not match.")).toBeVisible();
  expect(requests).toHaveLength(0);
  await page.getByLabel("Confirm password").fill("testing-password");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("status")).toContainText("Account created");
  expect(requests[0].body).toEqual({
    name: "Alex Morgan",
    email: "alex@example.com",
    password: "testing-password",
  });
});
for (const status of [409, 422]) {
  test("registration handles HTTP " + status, async ({ page }) => {
    await mockApi(page, { registerStatus: status });
    await fillRegistration(page);
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    await expect(
      page.getByText(
        status === 409
          ? "An account with this email already exists"
          : "This email address is not accepted",
      ),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/register$/);
  });
}
test("verified session restores after reload and logout clears it", async ({
  page,
}, testInfo) => {
  const requests = await mockApi(page);
  await signIn(page);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Welcome, Alex." }),
  ).toBeVisible();
  await expect(page.getByText("Not connected yet")).toHaveCount(4);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Welcome, Alex." }),
  ).toBeVisible();
  const meCalls = requests.filter((req) => req.path === "/api/auth/me");
  expect(meCalls.length).toBeGreaterThanOrEqual(2);
  expect(
    meCalls.every((req) => req.authorization === "Bearer opaque-test-token"),
  ).toBe(true);
  expect(requests.every((req) => req.path.startsWith("/api/auth/") || req.path.startsWith("/api/memory/"))).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("dashboard.png"),
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Create New Plan", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/plans\/new$/);
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), sessionKey),
  ).toBeNull();
  await page.goBack();
  await expect(page).toHaveURL(/\/login$/);
});
test("login returns to intended protected route and integrated shell links work", async ({
  page,
  isMobile,
}) => {
  await mockApi(page);
  await page.goto("/settings");
  await page.getByLabel("Email address").fill("alex@example.com");
  await page.getByLabel("Password", { exact: true }).fill("testing-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await page.route("**/api/plans", route => route.fulfill({ json: [] }));
  await page.route("**/api/memory", route => route.fulfill({ json: [] }));
  await page.route("**/api/memory/habits", route => route.fulfill({ json: [] }));
  await page.route("**/api/memory/consent", route => route.fulfill({ json: { memory_enabled: false } }));
  for (const [name, heading, placeholder] of [
    ["Planning History", "Planning History", true],
    ["What-If Simulator", "Select a Plan for What-If Analysis", false],
    ["Memory", "Planning Memory", false],
    ["Settings", "Settings", true],
  ]) {
    if (isMobile) await page.getByRole("button", { name: "Menu" }).click();
    await page.getByRole("link", { name, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
    if (placeholder) await expect(page.getByText("COMING LATER")).toBeVisible();
    else await expect(page.getByText("COMING LATER")).toBeHidden();
  }
});
test("invalid stored token is rejected by me and removed", async ({ page }) => {
  await mockApi(page, { meStatus: 401 });
  await page.addInitScript(
    ({ key }) =>
      sessionStorage.setItem(
        key,
        JSON.stringify({ token: "tampered", expiresAt: Date.now() + 60000 }),
      ),
    { key: sessionKey },
  );
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), sessionKey),
  ).toBeNull();
});
test("expired stored token cannot open protected content", async ({ page }) => {
  const requests = await mockApi(page);
  await page.addInitScript(
    ({ key }) =>
      sessionStorage.setItem(
        key,
        JSON.stringify({ token: "expired", expiresAt: Date.now() - 1 }),
      ),
    { key: sessionKey },
  );
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  expect(requests).toHaveLength(0);
});
test("active session expires and returns to login", async ({ page }) => {
  await mockApi(page, { expiresIn: 2 });
  await signIn(page);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page).toHaveURL(/\/login$/, { timeout: 6000 });
});
test("network failure on restoration offers retry without exposing the dashboard", async ({
  page,
}) => {
  await mockApi(page);
  await signIn(page);
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.route("**/api/auth/me", (route) => route.abort("failed"));
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Let’s reconnect" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Welcome, Alex." }),
  ).toHaveCount(0);
  await page.unroute("**/api/auth/me");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome, Alex." }),
  ).toBeVisible();
});
test("login waits for the server and does not submit twice", async ({
  page,
}) => {
  await mockApi(page);
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  await page.route("**/api/auth/login", async (route) => {
    await gate;
    await route.fulfill({
      json: {
        access_token: "opaque-test-token",
        token_type: "bearer",
        expires_in: 3600,
      },
    });
  });
  await signIn(page);
  await expect(
    page.getByRole("button", { name: "Signing in…" }),
  ).toBeDisabled();
  release();
  await expect(page).toHaveURL(/\/dashboard$/);
});
test("client validation avoids requests and network errors are readable", async ({
  page,
}) => {
  const requests = await mockApi(page);
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Enter a valid email address.")).toBeVisible();
  await expect(page.getByText("Enter your password.")).toBeVisible();
  expect(requests).toHaveLength(0);
  await page.route("**/api/auth/login", (route) => route.abort("failed"));
  await signIn(page);
  await expect(page.getByRole("alert")).toContainText(
    "Cannot reach the server",
  );
});
