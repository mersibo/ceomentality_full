import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
 testDir:'./tests/e2e',
 timeout:30_000,
 fullyParallel:true,
 reporter:'line',
 use:{baseURL:'http://127.0.0.1:4173',trace:'retain-on-failure',screenshot:'only-on-failure'},
 webServer:{command:'npm run preview',url:'http://127.0.0.1:4173',reuseExistingServer:true,timeout:60_000},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}]
});
