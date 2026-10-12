// Run with @playwright/test installed and the repository served on port 8080.
import { chromium, expect } from '@playwright/test';
import fs from 'node:fs/promises';
const out='artifacts/calibration-plots';await fs.mkdir(out,{recursive:true});const browser=await chromium.launch(),checks=[];
try{for(const width of [1280,390])for(const config of ['cardiorenal','cad','af']){
 const context=await browser.newContext({viewport:{width,height:950}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:8080/e156-submission/assets/CardioOracle.html?config='+config,{waitUntil:'load'});
  await page.evaluate(()=>{if(typeof dismissTutorial==='function')dismissTutorial();});
  const before=await page.evaluate(()=>JSON.stringify(MODEL));await page.locator('#tab-calibration').click();
  for(const id of ['calibPlotDiv','rocPlotDiv']){const chart=page.locator('#'+id);await expect(chart.locator('svg.main-svg').first()).toBeVisible();await expect.poll(()=>chart.evaluate(e=>e.data?.length||0)).toBeGreaterThan(1);expect(await chart.evaluate(e=>e.data.flatMap(t=>[...(t.x||[]),...(t.y||[])]).every(Number.isFinite))).toBe(true);}
  await expect(page.locator('#calibAucValue')).not.toHaveText('—');
  const chartData=await page.evaluate(()=>JSON.stringify(['calibPlotDiv','rocPlotDiv'].map(id=>document.getElementById(id).data)));
  await page.locator('#tab-training').click();await page.locator('#tab-calibration').click();await page.setViewportSize({width:width+30,height:970});
  for(const id of ['calibPlotDiv','rocPlotDiv'])await expect(page.locator('#'+id+' svg.main-svg').first()).toBeVisible();
  expect(await page.evaluate(()=>JSON.stringify(MODEL))).toBe(before);expect(await page.evaluate(()=>JSON.stringify(['calibPlotDiv','rocPlotDiv'].map(id=>document.getElementById(id).data)))).toBe(chartData);expect(errors).toEqual([]);
  await page.screenshot({path:out+'/'+config+'-'+width+'.png',fullPage:true});checks.push({config,width,passed:true,auc:await page.locator('#calibAucValue').innerText()});
 }finally{await context.close();}
}}finally{await browser.close();await fs.writeFile(out+'/results.json',JSON.stringify(checks,null,2));}
console.log(JSON.stringify({passed:checks.length,checks}));
