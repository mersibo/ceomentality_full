import { expect, test, type Page } from '@playwright/test';

async function authenticatedPage(page:Page,path='/candidates') {
 await page.addInitScript(()=>localStorage.setItem('ceomentality:session','active'));
 await page.goto(path);
 await expect(page.getByRole('banner')).toBeVisible();
}

test('signs in and opens the candidate workspace',async({page})=>{
 await page.goto('/login');
 await page.getByPlaceholder('Enter password').fill('demo-password');
 await page.getByRole('button',{name:/sign in/i}).click();
 await expect(page.getByRole('heading',{name:/candidate dossiers/i})).toBeVisible();
 await expect(page).toHaveURL(/\/candidates$/);
});

test('supports direct links for primary routes',async({page})=>{
 await authenticatedPage(page,'/access-codes');
 await expect(page.getByRole('heading',{name:/access codes/i})).toBeVisible();
 await page.getByRole('button',{name:'Analytics',exact:true}).click();
 await expect(page).toHaveURL(/\/analytics$/);
 await expect(page.getByRole('heading',{name:/analytics/i})).toBeVisible();
});

test('opens a candidate dossier with a stable URL and returns',async({page})=>{
 await authenticatedPage(page);
 await page.getByText('Alexei Petrov',{exact:true}).first().click();
 await expect(page).toHaveURL(/\/candidates\/alexei-petrov$/);
 await expect(page.getByRole('heading',{name:'Alexei Petrov'})).toBeVisible();
 await page.getByRole('button',{name:/back to dossiers/i}).click();
 await expect(page).toHaveURL(/\/candidates$/);
});

test('sign out clears the local session',async({page})=>{
 await authenticatedPage(page);
 await page.getByRole('button',{name:'CM',exact:true}).click();
 await page.getByRole('button',{name:/sign out/i}).click();
 await expect(page.getByRole('heading',{name:/welcome back/i})).toBeVisible();
 await expect(page.evaluate(()=>localStorage.getItem('ceomentality:session'))).resolves.toBeNull();
});

test('switches translated UI while keeping branded headings in English',async({page})=>{
 await authenticatedPage(page);
 await page.getByRole('button',{name:/switch interface language/i}).click();
 await expect(page.getByText('Фильтры',{exact:true})).toBeVisible();
 await expect(page.locator('.filter-head span')).toHaveAttribute('data-russian-text','true');
 await expect(page.locator('.filter-head span')).toHaveCSS('font-family',/Onest/);
 await expect(page.locator('.brand')).not.toHaveAttribute('data-russian-text');
 await expect(page.locator('.main-nav button').nth(1)).not.toHaveText('Access Codes');
 await expect(page.getByRole('heading',{name:'candidate dossiers'})).toBeVisible();
 await expect(page.evaluate(()=>document.documentElement.lang)).resolves.toBe('ru');
});

test('desktop header toggle collapses and restores the sidebar',async({page})=>{
 await authenticatedPage(page,'/candidates/alexei-petrov');
 const toggle=page.getByRole('button',{name:/hide filters/i});
 await toggle.click();
 await expect(page.locator('.sidebar')).toHaveCSS('width','0px');
 await page.locator('.sidebar-reveal-zone').hover();
 await page.getByRole('button',{name:/show filters/i}).click();
 await expect(page.locator('.sidebar')).toHaveCSS('width','260px');
});

test('does not replace the workspace with a loading screen during navigation',async({page})=>{
 await authenticatedPage(page);
 const loading=page.getByText('Loading workspace…',{exact:true});
 for(const route of ['Access Codes','Analytics','Candidate Dossiers']){
  await page.getByRole('button',{name:route,exact:true}).click();
  await expect(loading).toHaveCount(0);
 }
});

test('keeps profile page titles in English in the Russian interface',async({page})=>{
 await authenticatedPage(page,'/profile');
 await page.getByRole('button',{name:/switch interface language/i}).click();
 await expect(page.locator('.profile-page .pretitle')).toHaveText('Account & access');
 await expect(page.getByRole('heading',{name:'profile settings'})).toBeVisible();
});

test('renders Profile & settings as one label without splitting the ampersand',async({page})=>{
 await authenticatedPage(page);
 await page.getByRole('button',{name:'CM',exact:true}).click();
 const profileAction=page.getByRole('button',{name:/Profile & settings/i});
 await expect(profileAction).toBeVisible();
 expect(await profileAction.evaluate(element=>({
  text:element.textContent?.replace(/\s+/g,' ').trim(),
  elements:element.childElementCount
 }))).toEqual({text:'Profile & settings',elements:1});
});
