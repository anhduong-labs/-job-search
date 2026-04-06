#!/usr/bin/env node
/**
 * crawl_playwright.js - Crawl Web3 jobs với Playwright
 * Includes: web3career, cryptojobslist, LinkedIn, Indeed, tracked companies
 * Output: ~/.openclaw/workspace/jobs_playwright.json
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const WORKSPACE = path.join(process.env.HOME, '.openclaw/workspace');
const OUTPUT_FILE = path.join(WORKSPACE, 'jobs_playwright.json');
const PORTALS_FILE = path.join(process.env.HOME, '.openclaw/skills/job-scanner/portals.yml');

// LinkedIn credentials (optional - set via env vars)
const LINKEDIN_EMAIL = process.env.LINKEDIN_EMAIL || '';
const LINKEDIN_PASSWORD = process.env.LINKEDIN_PASSWORD || '';

// Simple YAML parser
function parseSimpleYAML(content) {
  const lines = content.split('\n');
  const result = { tracked_companies: [] };
  let currentCompany = null;
  
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('- name:')) {
      if (currentCompany) result.tracked_companies.push(currentCompany);
      currentCompany = { name: trimmed.split(':')[1].trim() };
    } else if (currentCompany) {
      if (trimmed.startsWith('careers_url:')) {
        currentCompany.careers_url = trimmed.split('careers_url:')[1].trim();
      } else if (trimmed.startsWith('enabled:')) {
        currentCompany.enabled = trimmed.includes('true');
      }
    }
  }
  if (currentCompany) result.tracked_companies.push(currentCompany);
  return result;
}

async function crawlLinkedIn(page) {
  console.log('  💼 Crawling LinkedIn...');
  const jobs = [];
  
  const keywords = [
    'web3 ecosystem manager',
    'crypto research analyst', 
    'blockchain business development',
    'defi partnerships',
    'web3 growth'
  ];
  
  // Login if credentials provided
  if (LINKEDIN_EMAIL && LINKEDIN_PASSWORD) {
    try {
      console.log('    🔐 Logging in to LinkedIn...');
      await page.goto('https://www.linkedin.com/login', { timeout: 15000 });
      await page.fill('#username', LINKEDIN_EMAIL);
      await page.fill('#password', LINKEDIN_PASSWORD);
      await page.click('button[type="submit"]');
      await page.waitForTimeout(3000);
      console.log('    ✅ Logged in');
    } catch (e) {
      console.log(`    ⚠️  Login failed: ${e.message}, continuing without login`);
    }
  }
  
  for (const keyword of keywords.slice(0, 3)) {
    try {
      const url = `https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(keyword)}&location=Remote&f_WT=2`;
      await page.goto(url, { timeout: 15000, waitUntil: 'domcontentloaded' });
      
      // Wait for job cards
      await page.waitForSelector('.job-card-container, .jobs-search__results-list li', { timeout: 10000 }).catch(() => {});
      
      // Scroll to load more
      await page.evaluate(async () => {
        for (let i = 0; i < 3; i++) {
          window.scrollTo(0, document.body.scrollHeight);
          await new Promise(r => setTimeout(r, 1500));
        }
      });
      
      // Extract jobs
      const pageJobs = await page.$$eval('.job-card-container, .jobs-search__results-list li', (cards) =>
        cards.map(card => {
          const titleEl = card.querySelector('.job-card-list__title, .base-search-card__title');
          const companyEl = card.querySelector('.job-card-container__company-name, .base-search-card__subtitle');
          const locationEl = card.querySelector('.job-card-container__metadata-item, .job-search-card__location');
          const linkEl = card.querySelector('a');
          
          return {
            source: 'linkedin',
            title: titleEl?.innerText?.trim() || '',
            company: companyEl?.innerText?.trim() || '',
            location: locationEl?.innerText?.trim() || 'Remote',
            url: linkEl?.href || '',
            date_crawled: new Date().toISOString().split('T')[0],
            salary: '',
            description: ''
          };
        })
      );
      
      jobs.push(...pageJobs.filter(j => j.title && j.url && j.url.includes('linkedin.com')));
      console.log(`    ✅ Keyword "${keyword}": ${pageJobs.length} jobs`);
      
      await page.waitForTimeout(2000); // Rate limit
      
    } catch (e) {
      console.log(`    ⚠️  Keyword "${keyword}": ${e.message}`);
    }
  }
  
  console.log(`    📊 Total LinkedIn: ${jobs.length} jobs`);
  return jobs;
}

async function crawlIndeed(page) {
  console.log('  💼 Crawling Indeed...');
  const jobs = [];
  
  const keywords = [
    'web3 remote',
    'crypto remote', 
    'blockchain remote',
    'defi remote'
  ];
  
  for (const keyword of keywords.slice(0, 3)) {
    try {
      const url = `https://www.indeed.com/jobs?q=${encodeURIComponent(keyword)}&l=Remote&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11`;
      await page.goto(url, { timeout: 15000, waitUntil: 'domcontentloaded' });
      
      // Wait for job cards
      await page.waitForSelector('.job_seen_beacon, .jobsearch-ResultsList li', { timeout: 10000 }).catch(() => {});
      
      // Extract jobs
      const pageJobs = await page.$$eval('.job_seen_beacon, .jobsearch-ResultsList > li', (cards) =>
        cards.map(card => {
          const titleEl = card.querySelector('.jobTitle, h2.jobTitle a');
          const companyEl = card.querySelector('[data-testid="company-name"], .companyName');
          const locationEl = card.querySelector('[data-testid="text-location"], .companyLocation');
          const linkEl = card.querySelector('h2.jobTitle a, .jcs-JobTitle');
          
          return {
            source: 'indeed',
            title: titleEl?.innerText?.trim() || '',
            company: companyEl?.innerText?.trim() || '',
            location: locationEl?.innerText?.trim() || 'Remote',
            url: linkEl?.href ? 'https://www.indeed.com' + linkEl.getAttribute('href') : '',
            date_crawled: new Date().toISOString().split('T')[0],
            salary: '',
            description: ''
          };
        })
      );
      
      jobs.push(...pageJobs.filter(j => j.title && j.url));
      console.log(`    ✅ Keyword "${keyword}": ${pageJobs.length} jobs`);
      
      await page.waitForTimeout(2000); // Rate limit
      
    } catch (e) {
      console.log(`    ⚠️  Keyword "${keyword}": ${e.message}`);
    }
  }
  
  console.log(`    📊 Total Indeed: ${jobs.length} jobs`);
  return jobs;
}

async function crawlWeb3Career(page) {
  console.log('  🌐 Crawling web3.career...');
  const jobs = [];
  
  const keywords = ['ecosystem', 'research', 'analyst', 'business development', 'partnerships'];
  
  for (const keyword of keywords.slice(0, 3)) {
    try {
      const url = `https://web3.career/remote+web3-jobs?search=${encodeURIComponent(keyword)}`;
      await page.goto(url, { timeout: 15000, waitUntil: 'domcontentloaded' });
      
      // Wait for table rows to load
      await page.waitForSelector('table tbody tr', { timeout: 10000 }).catch(() => {});
      await page.waitForTimeout(3000); // Extra wait for dynamic content
      
      await page.evaluate(async () => {
        for (let i = 0; i < 3; i++) {
          window.scrollTo(0, document.body.scrollHeight);
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      });
      
      // Extract jobs from table rows with data-jobid
      const pageJobs = await page.$$eval('table tbody tr[data-jobid]', (rows) => 
        rows.map(row => {
          // Get the main job link (first link with data-turbo-frame="job")
          const jobLink = row.querySelector('a[data-turbo-frame="job"]');
          const title = row.querySelector('td h2')?.innerText?.trim() || '';
          const company = row.querySelector('h3')?.innerText?.trim() || '';
          const url = jobLink?.href || '';
          
          // Try to extract location and salary from other table cells
          const cells = Array.from(row.querySelectorAll('td'));
          let location = 'Remote';
          let salary = '';
          
          // Look for location/salary in td text content
          cells.forEach(cell => {
            const text = cell.innerText?.trim();
            if (text && text.includes('$')) {
              salary = text;
            }
          });
          
          return {
            source: 'web3career',
            title,
            company,
            location,
            salary,
            url,
            date_crawled: new Date().toISOString().split('T')[0],
            description: ''
          };
        })
      );
      
      jobs.push(...pageJobs.filter(j => j.title && j.url));
      console.log(`    ✅ Keyword "${keyword}": ${pageJobs.length} jobs`);
      
    } catch (e) {
      console.log(`    ⚠️  Keyword "${keyword}": ${e.message}`);
    }
  }
  
  console.log(`    📊 Total web3career: ${jobs.length} jobs`);
  return jobs;
}

async function crawlTrackedCompany(page, company) {
  console.log(`  🏢 Crawling ${company.name}...`);
  const jobs = [];
  
  try {
    await page.goto(company.careers_url, { timeout: 15000, waitUntil: 'domcontentloaded' });
    
    await page.waitForSelector('.opening, .job-post, .posting, [data-qa="job"]', { timeout: 10000 }).catch(() => {});
    
    const selectors = [
      '.opening',
      '.job-post',
      '.posting',
      '[data-qa="job"]'
    ];
    
    for (const selector of selectors) {
      const elements = await page.$$(selector);
      if (elements.length > 0) {
        const pageJobs = await page.$$eval(selector, (items, companyName) =>
          items.map(item => ({
            source: 'tracked_company',
            title: item.querySelector('a, h3, h4')?.innerText?.trim() || '',
            company: companyName,
            location: item.querySelector('.location')?.innerText?.trim() || 'Remote',
            url: item.querySelector('a')?.href || '',
            date_crawled: new Date().toISOString().split('T')[0],
            salary: '',
            description: ''
          })), company.name
        );
        
        jobs.push(...pageJobs.filter(j => j.title && j.url));
        break;
      }
    }
    
    console.log(`    ✅ ${company.name}: ${jobs.length} jobs`);
    
  } catch (e) {
    console.log(`    ⚠️  ${company.name}: ${e.message}`);
  }
  
  return jobs;
}

async function main() {
  console.log('🔍 Bắt đầu crawl việc làm Web3 với Playwright...');
  console.log(`   Thời gian: ${new Date().toLocaleString('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh'})}`);
  console.log();
  
  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.setExtraHTTPHeaders({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
  });
  
  const allJobs = [];
  
  // 1. LinkedIn
  const linkedInJobs = await crawlLinkedIn(page);
  allJobs.push(...linkedInJobs);
  
  // 2. Indeed
  const indeedJobs = await crawlIndeed(page);
  allJobs.push(...indeedJobs);
  
  // 3. web3career
  const web3CareerJobs = await crawlWeb3Career(page);
  allJobs.push(...web3CareerJobs);
  
  // 4. Tracked companies
  if (fs.existsSync(PORTALS_FILE)) {
    const yaml = fs.readFileSync(PORTALS_FILE, 'utf8');
    const config = parseSimpleYAML(yaml);
    
    for (const company of config.tracked_companies.filter(c => c.enabled && c.careers_url)) {
      const companyJobs = await crawlTrackedCompany(page, company);
      allJobs.push(...companyJobs);
    }
  } else {
    console.log('  ℹ️  No portals.yml found, skipping tracked companies');
  }
  
  await browser.close();
  
  // Deduplicate
  const seen = new Set();
  const uniqueJobs = allJobs.filter(job => {
    if (seen.has(job.url)) return false;
    seen.add(job.url);
    return true;
  });
  
  // Save
  fs.mkdirSync(WORKSPACE, { recursive: true });
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(uniqueJobs, null, 2));
  
  console.log();
  console.log('✅ Crawl xong!');
  console.log(`   Total jobs: ${uniqueJobs.length} (sau deduplicate)`);
  console.log(`   - LinkedIn: ${uniqueJobs.filter(j => j.source === 'linkedin').length}`);
  console.log(`   - Indeed: ${uniqueJobs.filter(j => j.source === 'indeed').length}`);
  console.log(`   - web3career: ${uniqueJobs.filter(j => j.source === 'web3career').length}`);
  console.log(`   - tracked companies: ${uniqueJobs.filter(j => j.source === 'tracked_company').length}`);
  console.log(`💾 Lưu vào: ${OUTPUT_FILE}`);
}

main().catch(console.error);
