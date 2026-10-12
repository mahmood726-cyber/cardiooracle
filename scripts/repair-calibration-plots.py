from pathlib import Path
import hashlib
p=Path('e156-submission/assets/CardioOracle.html');raw=p.read_bytes()
assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()=='0faa6383d223a068b3f6465746956eb004baa578'
t=raw.decode();old='    if (!window.MODEL || !MODEL.temporal_validation) return;'
assert t.count(old)==1
new="""    // MODEL is lexical. Never substitute in-sample data for missing validation.
    if (typeof MODEL === 'undefined' || !MODEL.temporal_validation || !Array.isArray(MODEL.temporal_validation.trial_predictions)) {
      for (const id of ['calibPlotDiv', 'rocPlotDiv']) {
        const plot = document.getElementById(id);
        if (!plot) continue;
        if (typeof Plotly !== 'undefined' && plot.data) Plotly.purge(plot);
        plot.replaceChildren();
        const message = document.createElement('p');
        message.setAttribute('role', 'status');
        message.style.cssText = 'padding:1.5rem;line-height:1.6';
        message.textContent = 'Temporal validation predictions are not included for this model. Calibration and ROC plots require held-out predictions and outcomes; no substitute or demonstration plot is shown.';
        plot.appendChild(message);
        plot.dataset.plotState = 'unavailable';
      }
      return;
    }"""
newline='\r\n' if b'\r\n' in raw else '\n'
t=t.replace(old,new.replace('\n',newline),1);p.write_bytes(t.encode())
p=Path('tests/plot-regressions/calibration.mjs');t=p.read_text()
old="  const before=await page.evaluate(()=>JSON.stringify(MODEL));await page.locator('#tab-calibration').click();"
new="""  const before=await page.evaluate(()=>JSON.stringify(MODEL));await page.locator('#tab-calibration').click();
  if(config==='af') {
    expect(await page.evaluate(()=>!!MODEL.temporal_validation)).toBe(false);
    for(const id of ['calibPlotDiv','rocPlotDiv']) {
      await expect(page.locator('#'+id)).toHaveAttribute('data-plot-state','unavailable');
      await expect(page.locator('#'+id)).toContainText('Temporal validation predictions are not included');
      await expect(page.locator('#'+id+' svg')).toHaveCount(0);
    }
    expect(await page.evaluate(()=>JSON.stringify(MODEL))).toBe(before);
    expect(errors).toEqual([]);
    await page.screenshot({path:out+'/'+config+'-'+width+'.png',fullPage:true});
    checks.push({config,width,passed:true,state:'explicit missing-validation prerequisite'});
    continue;
  }"""
assert t.count(old)==1;p.write_text(t.replace(old,new,1))
