const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { randomBytes } = require('node:crypto');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const runtimeModules = path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || require.resolve('playwright', { paths: [root, runtimeModules] }));
const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const output = path.resolve(root, process.env.ARCTIC_QA_OUTPUT_DIR || 'frontend/test-results/roles-e2e');
const runId = `${Date.now()}-${randomBytes(3).toString('hex')}`;
const password = `QaRoles9-${randomBytes(18).toString('hex')}`;
const report = { runId, startedAt: new Date().toISOString(), base, fictionalFixtures: true, checks: [], screenshots: [], browserErrors: [], apiErrors: [] };
const projectTitle = `Ролевой маршрут Арктики ${runId}`;
const reviewComment = 'Фиктивная рецензия QA: проверены комплектность, критерии и публикация результата. Это не конкурсная экспертная оценка.';
const contexts = [];
const pages = {};
let fixture;
let browser;
let activePage;
let nextApiRequestAt = Date.now();

function pass(name, details = {}) { report.checks.push({ name, status: 'passed', ...details }); }
function match(method, suffix) { return response => response.request().method() === method && new URL(response.url()).pathname.endsWith(suffix); }
async function responseJson(pending, expectedStatus = 200) {
  const response = await pending;
  assert.equal(response.status(), expectedStatus, `${response.request().method()} ${new URL(response.url()).pathname}`);
  return response.json();
}
async function snapshot(page, name) {
  await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: true });
  await fs.writeFile(path.join(output, `${name}.txt`), await page.locator('main').ariaSnapshot());
  report.screenshots.push(`${name}.png`);
}
async function responsive(page, name) {
  for (const width of [1440, 834, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => document.fonts.ready);
    const size = await page.evaluate(() => ({ viewport: innerWidth, page: document.documentElement.scrollWidth }));
    assert(size.page <= size.viewport + 1, `${name} overflows at ${width}: ${size.page}`);
    await snapshot(page, `${name}-${width}`);
    pass('Responsive layout without horizontal overflow', { screen: name, width });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}
async function login(role) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, timezoneId: 'Asia/Yakutsk', locale: 'ru-RU', reducedMotion: 'reduce', acceptDownloads: true });
  contexts.push(context);
  // Five browser roles share one local IP; pace QA without changing server limits.
  await context.route('**/api/**', async route => {
    const slot = Math.max(Date.now(), nextApiRequestAt);
    nextApiRequestAt = slot + 1100;
    await new Promise(resolve => setTimeout(resolve, slot - Date.now()));
    await route.continue();
  });
  const page = await context.newPage();
  pages[role] = page;
  activePage = page;
  page.setDefaultTimeout(20000);
  page.on('pageerror', error => report.browserErrors.push({ role, message: error.message }));
  page.on('response', response => {
    if (response.url().includes('/api/') && response.status() >= 400) report.apiErrors.push({ role, method: response.request().method(), path: new URL(response.url()).pathname, status: response.status() });
  });
  page.on('dialog', dialog => dialog.accept());
  await page.goto(`${base}/#login`);
  await page.locator('#login-form').waitFor();
  await page.locator('#email').fill(fixture.users[role].email);
  await page.locator('#password').fill(password);
  const signedIn = page.waitForResponse(match('POST', '/auth/login'));
  await page.locator('#login-form button[type="submit"]').click();
  await responseJson(signedIn);
  if (['admin', 'commission'].includes(role)) {
    await page.locator('.console-sidebar a[data-route="workspace"]').click();
  }
  await page.locator(role === 'participant' ? '[data-action="new-project"]' : '#work-filter-form').first().waitFor();
  if (role === 'participant') {
    assert.equal(await page.locator('[data-action="new-project"]').first().isEnabled(), false);
    const api = `${base}/api/v1`;
    const student = await page.evaluate(() => JSON.parse(sessionStorage.getItem('arctic-session')));
    const organizerLogin = await context.request.post(`${api}/auth/login`, {
      data: { email: fixture.users.admin.email, password },
    });
    assert.equal(organizerLogin.status(), 200);
    const organizer = await organizerLogin.json();
    const bankReply = await context.request.get(`${api}/admin/questions?limit=200`, {
      headers: { Authorization: `Bearer ${organizer.access_token}` },
    });
    assert.equal(bankReply.status(), 200);
    const bank = await bankReply.json();
    const headers = { Authorization: `Bearer ${student.access_token}` };
    const started = await context.request.post(`${api}/quiz/attempts`, { headers });
    assert.equal(started.status(), 200);
    const attempt = await started.json();
    assert.ok(attempt.questions.every(question => !('correct_option_ids' in question)));
    const answers = Object.fromEntries(attempt.questions.map(question => [
      question.id, bank.find(item => item.id === question.id).correct_option_ids,
    ]));
    const submitted = await context.request.post(`${api}/quiz/attempts/${attempt.id}/submit`, {
      headers, data: { answers },
    });
    assert.equal(submitted.status(), 200);
    assert.equal((await submitted.json()).passed, true);
    await page.reload();
    await page.waitForFunction(() => {const button = document.querySelector('[data-action="new-project"]');return button && !button.disabled;});
    pass('Second stage opens only after a server-graded passing quiz');
  }
  pass('Role login through UI', { role });
  return page;
}
async function openRoleProject(page, projectId) {
  activePage = page;
  await page.locator(`[data-role-project="${projectId}"]`).first().click();
  await page.getByRole('heading', { name: projectTitle, exact: true }).waitFor();
}
async function waitNotice(page, text) { await page.locator('main .notice').filter({ hasText: text }).first().waitFor(); }

(async () => {
  await fs.mkdir(output, { recursive: true });
  try {
    const previous = JSON.parse(await fs.readFile(path.join(output, 'report.json'), 'utf8'));
    await fs.copyFile(path.join(output, 'report.json'), path.join(output, `report-${previous.runId}.json`));
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  fixture = JSON.parse(execFileSync(path.join(root, 'backend/.venv/Scripts/python.exe'), [path.join(__dirname, 'create_roles_fixture.py')], {
    cwd: path.join(root, 'backend'), encoding: 'utf8',
    env: { ...process.env, ARCTIC_QA_RUN_ID: runId, ARCTIC_QA_PASSWORD: password },
  }));
  report.fixtureUserIds = Object.fromEntries(Object.entries(fixture.users).map(([role, user]) => [role, user.id]));
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const participant = await login('participant');
    await participant.locator('[data-action="new-project"]').first().click();
    await participant.locator('#project-title').fill(projectTitle);
    await participant.locator('#project-nomination').selectOption(fixture.nomination_id);
    await participant.locator('#project-abstract').fill('Фиктивный исследовательский материал для проверки полного ролевого маршрута: подача, допуск, экспертиза, публикация и защита.');
    await participant.locator('#project-file').setInputFiles(fixture.files.document);
    await participant.locator('#project-presentation').setInputFiles(fixture.files.presentation);
    const created = participant.waitForResponse(match('POST', '/projects'));
    await participant.getByRole('button', { name: 'Сохранить черновик', exact: true }).click();
    const project = await responseJson(created, 201);
    report.projectId = project.id;
    await participant.locator('.file-list .file-item').nth(1).waitFor();
    await participant.locator('#project-form[aria-busy="true"]').waitFor({ state: 'detached' });
    assert(participant.url().endsWith(`#project/${project.id}`), 'Draft URL must preserve its project id');
    const loaded = participant.waitForResponse(match('GET', `/projects/${project.id}`));
    await participant.reload();
    const draft = await responseJson(loaded);
    assert.equal(draft.id, project.id);
    assert.equal(draft.status, 'draft');
    assert.deepEqual(draft.files.map(file => file.kind).sort(), ['document', 'presentation']);
    await participant.locator('#project-form').waitFor();
    assert.equal(await participant.locator('#project-title').inputValue(), projectTitle);
    pass('Draft id, fields and two material types persist after reload', { projectId: project.id, fileKinds: ['document', 'presentation'] });
    await responsive(participant, '01-participant-draft');
    const submitted = participant.waitForResponse(match('POST', `/projects/${project.id}/submit`));
    await participant.getByRole('button', { name: 'Отправить проект', exact: true }).click();
    assert.equal((await responseJson(submitted)).status, 'submitted');
    await participant.getByText('На проверке', { exact: true }).waitFor();
    pass('Participant submits project through UI');

    const admin = await login('admin');
    await admin.locator('#work-query').fill(projectTitle);
    await admin.locator('#work-filter-form button[type="submit"]').click();
    await openRoleProject(admin, project.id);
    const correction = 'QA: уточните метод исследования и поясните вывод.';
    await admin.locator('#moderation-status').selectOption('rejected');
    await admin.locator('#moderation-comment').fill(correction);
    await admin.getByRole('button', { name: 'Проверить решение', exact: true }).click();
    const returned = admin.waitForResponse(match('POST', `/admin/projects/${project.id}/moderate`));
    await admin.getByRole('button', { name: 'Подтвердить решение', exact: true }).click();
    assert.equal((await responseJson(returned)).status, 'rejected');
    pass('Admin returns project with an explanatory comment');
    await participant.locator('[data-action="refresh-project"]').click();
    await participant.getByText(correction, { exact: true }).waitFor();
    const reopened = participant.waitForResponse(match('POST', `/projects/${project.id}/reopen`));
    await participant.getByRole('button', { name: 'Вернуть в черновик', exact: true }).click();
    assert.equal((await responseJson(reopened)).status, 'draft');
    await participant.locator('#project-form').waitFor();
    const correctedAbstract = 'Фиктивная исправленная работа QA: указан метод сравнения источников, описано наблюдение и уточнён вывод исследования.';
    await participant.locator('#project-abstract').fill(correctedAbstract);
    const corrected = participant.waitForResponse(match('PATCH', `/projects/${project.id}`));
    const correctedRead = participant.waitForResponse(match('GET', `/projects/${project.id}`));
    await participant.getByRole('button', { name: 'Сохранить черновик', exact: true }).click();
    const correctedDraft = await responseJson(corrected);
    assert.equal(correctedDraft.abstract, correctedAbstract);
    assert.equal((await responseJson(correctedRead)).files.length, 2);
    await participant.reload();
    await participant.locator('#project-form').waitFor();
    assert.equal(await participant.locator('#project-abstract').inputValue(), correctedAbstract);
    pass('Returned project reopens and corrected draft preserves both attachments');
    const resubmitted = participant.waitForResponse(match('POST', `/projects/${project.id}/submit`));
    await participant.getByRole('button', { name: 'Отправить проект', exact: true }).click();
    assert.equal((await responseJson(resubmitted)).status, 'submitted');
    pass('Participant resubmits corrected project through UI');
    await admin.reload();
    await admin.locator('#moderation-form').waitFor();
    await admin.locator('#moderation-comment').fill('QA: документ и презентация приняты для проверки ролевого маршрута.');
    await admin.getByRole('button', { name: 'Проверить решение', exact: true }).click();
    const moderated = admin.waitForResponse(match('POST', `/admin/projects/${project.id}/moderate`));
    await admin.getByRole('button', { name: 'Подтвердить решение', exact: true }).click();
    assert.equal((await responseJson(moderated)).status, 'admitted');
    await admin.locator('#assignment-form').waitFor();
    pass('Admin admits project through confirmed UI action');
    await responsive(admin, '02-admin-admitted');
    await admin.locator(`#assignment-form input[value="${fixture.users.expert.id}"]`).check();
    const assigned = admin.waitForResponse(match('POST', `/admin/projects/${project.id}/assign`));
    await admin.getByRole('button', { name: 'Назначить выбранных', exact: true }).click();
    const assignment = await responseJson(assigned);
    assert.equal(assignment.assigned, 1);
    const assignmentId = assignment.assignments[0].id;
    await waitNotice(admin, 'Добавлено назначений: 1.');
    pass('Admin assigns only the isolated fixture expert', { assignmentId });

    const expert = await login('expert');
    await openRoleProject(expert, project.id);
    await expert.locator('#expert-review-form').waitFor();
    const pdfFile = draft.files.find(file => file.kind === 'document');
    await expert.locator(`[data-role-preview="${pdfFile.id}"]`).click();
    await expert.locator('#dialog .pdf-preview').waitFor();
    assert((await expert.locator('#dialog .pdf-preview').getAttribute('src')).startsWith('blob:'));
    await expert.locator('#dialog [data-action="close"]').click();
    pass('Expert opens the private project PDF through authenticated UI');
    const scoreInputs = expert.locator('#expert-review-form input[type="number"]');
    const criterionCount = await scoreInputs.count();
    assert(criterionCount > 0);
    for (let index = 0; index < criterionCount; index++) {
      const input = scoreInputs.nth(index);
      await input.fill(String(Number(await input.getAttribute('max')) * 0.8));
    }
    await expert.locator('#review-comment').fill(reviewComment);
    await expert.getByRole('button', { name: 'Сохранить черновик', exact: true }).click();
    await expert.reload();
    await expert.locator('#expert-review-form').waitFor();
    assert.equal(await expert.locator('#review-comment').inputValue(), reviewComment);
    assert.equal(await expert.locator('#weighted-preview').textContent(), '80');
    pass('Expert draft survives reload and weighted preview is 80/100', { criterionCount });
    await responsive(expert, '03-expert-scoring');
    await expert.getByRole('button', { name: 'Проверить и отправить', exact: true }).click();
    const reviewed = expert.waitForResponse(match('POST', `/expert/assignments/${assignmentId}/review`));
    await expert.getByRole('button', { name: 'Отправить рецензию', exact: true }).click();
    const review = await responseJson(reviewed, 201);
    assert.equal(review.weighted_score, 80);
    await waitNotice(expert, 'Твоя рецензия принята');
    assert.equal(await expert.locator('#expert-review-form').count(), 0);
    pass('Expert submits all criteria and server computes 80/100', { reviewId: review.id, weightedScore: review.weighted_score });

    activePage = participant;
    await participant.reload();
    await participant.getByRole('heading', { name: 'Результаты экспертизы', exact: true }).waitFor();
    assert.equal(await participant.locator('.review-card').count(), 0);
    await participant.getByText('Ещё не опубликованы', { exact: true }).waitFor();
    pass('Participant cannot see unreleased expert review');
    activePage = admin;
    await admin.reload();
    await admin.getByRole('button', { name: 'Опубликовать результаты', exact: true }).click();
    const published = admin.waitForResponse(match('POST', `/admin/projects/${project.id}/publish`));
    await admin.getByRole('button', { name: 'Опубликовать', exact: true }).click();
    assert.equal((await responseJson(published)).reviews_released, true);
    await waitNotice(admin, 'Результаты опубликованы');
    pass('Admin publishes the completed review through UI');
    const defenseDate = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000);
    const defenseLocal = await admin.evaluate(value => {
      const date = new Date(value);
      const pad = number => String(number).padStart(2, '0');
      return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }, defenseDate.toISOString());
    await admin.locator('#defense-time').fill(defenseLocal);
    await admin.locator('#defense-link').fill('https://example.com/qa-defense');
    await admin.locator('#defense-description').fill('Фиктивная встреча QA: не подключаться, ссылка используется только для проверки интерфейса.');
    const scheduled = admin.waitForResponse(match('POST', '/admin/defenses'));
    await admin.getByRole('button', { name: 'Назначить встречу', exact: true }).click();
    const defense = await responseJson(scheduled, 201);
    await waitNotice(admin, 'Защита назначена');
    pass('Admin schedules defense through UI', { defenseId: defense.id, startsAt: defense.starts_at, displayTimezone: 'Asia/Yakutsk' });

    activePage = participant;
    await participant.reload();
    await participant.locator('.review-card').waitFor();
    assert.equal((await participant.locator('.review-comment').allTextContents()).includes(reviewComment), true);
    await participant.getByRole('heading', { name: 'Защита проекта', exact: true }).waitFor();
    assert.equal(await participant.getByRole('link', { name: 'Открыть встречу' }).getAttribute('href'), 'https://example.com/qa-defense');
    await responsive(participant, '04-participant-results');
    pass('Participant sees published score, comment and scheduled defense');

    const commission = await login('commission');
    await commission.locator('#work-query').fill(projectTitle);
    await commission.locator('#work-filter-form button[type="submit"]').click();
    await openRoleProject(commission, project.id);
    await commission.locator('.review-card').waitFor();
    for (const selector of ['#moderation-form', '#assignment-form', '#expert-review-form', '#defense-form', '[data-role-action="confirm-publish"]']) assert.equal(await commission.locator(selector).count(), 0, `Commission must not have ${selector}`);
    await commission.getByRole('link', { name: 'Работы конкурса', exact: true }).click();
    await commission.getByRole('link', { name: 'Результаты', exact: true }).click();
    await commission.locator('#ranking-filter-form').waitFor();
    const rankingRow = commission.locator('.ranking-row').filter({ hasText: projectTitle });
    await rankingRow.waitFor();
    assert.equal(await rankingRow.locator('.ranking-score strong').textContent(), '80');
    await responsive(commission, '05-commission-ranking');
    pass('Commission reads review and calculated ranking without editing controls');
    const commissionToken = await commission.evaluate(() => JSON.parse(sessionStorage.getItem('arctic-session')).access_token);
    const forbidden = await commission.request.post(`${base}/api/v1/admin/projects/${project.id}/publish`, { headers: { Authorization: `Bearer ${commissionToken}` } });
    assert.equal(forbidden.status(), 403);
    pass('Server rejects commission write even outside the UI', { httpStatus: 403 });

    const teacher = await login('teacher');
    await teacher.locator('.student-list').getByText(fixture.users.participant.name, { exact: true }).waitFor();
    assert.equal(await teacher.locator('.student-list article').count(), 1);
    await openRoleProject(teacher, project.id);
    await teacher.locator('.review-card').waitFor();
    await teacher.getByRole('heading', { name: 'Защита проекта', exact: true }).waitFor();
    assert.equal(await teacher.locator('#expert-review-form, #moderation-form, #defense-form').count(), 0);
    await responsive(teacher, '06-teacher-project');
    pass('Linked teacher reads own participant project, published review and defense');
    assert.deepEqual(report.browserErrors, []);
    assert.deepEqual(report.apiErrors, []);
    pass('No browser exceptions or unexpected API failures');
    report.status = 'passed';
  } catch (error) {
    report.status = 'failed';
    report.failure = { message: error.message, stack: error.stack };
    if (activePage) await snapshot(activePage, 'failure').catch(() => {});
    process.exitCode = 1;
  } finally {
    report.finishedAt = new Date().toISOString();
    await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    for (const context of contexts) await context.close();
    await browser?.close();
  }
  console.log(JSON.stringify({ status: report.status, checks: report.checks.length, failure: report.failure?.message, report: path.join(output, 'report.json') }));
})().catch(error => { console.error(error.message); process.exitCode = 1; });
