"""Browser review acceptance using precomputed real new-video inputs, no refit."""
import re
import copy
import json
import os
from pathlib import Path
import shutil
import unittest
from support import browser as shared

@unittest.skipUnless(os.getenv('BETALAB_INPUT_BROWSER')=='1','Requires browser opt-in')
class InputBrowserTest(unittest.TestCase):
    historical_display_only = True
    @classmethod
    def setUpClass(cls):shared.setup_browser(cls)
    @classmethod
    def tearDownClass(cls):shared.teardown_browser(cls)
    @classmethod
    def start(cls,name,cmd):shared.start(cls,name,cmd)
    def test_review(self):
        from backend.compute import service,storage
        from backend.database import database
        from playwright.sync_api import sync_playwright,expect
        clip=Path('backend/compute/runs/new-inputs-probe/new-video.mp4')
        with clip.open('rb') as f:
            response=self.alice.post('/api/videos',data=dict(route_id='r1',visibility='private',title='New input browser fixture'),files={'video':('new.mp4',f,'video/mp4')})
        video_id=response.json()['id'];response=self.alice.post('/api/tasks/upload-analysis/'+video_id)
        task=response.json();self.assertEqual(response.status_code,202,response.text)
        report=Path('backend/compute/runs/new-inputs-acceptance/validation.json')
        result=copy.deepcopy(json.loads(report.read_text())['task']['result']);result['source_video_id']=video_id
        for a in result['artifacts'].values():
            original=report.parent/a['storage_key'];self.assertEqual(storage.digest(original),a['sha256'])
            target=self.output/a['storage_key'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
        with database() as db:
            row=db.execute("UPDATE compute_tasks SET state='running' WHERE id=%s RETURNING *",(task['id'],)).fetchone();service.finish(db,row,result=result)
        with sync_playwright() as p:
            browser=p.chromium.launch();page=browser.new_page(viewport={'width':390,'height':844})
            page.goto('http://127.0.0.1:5177')
            page.get_by_label('Username',exact=True).fill('phase2alice');page.get_by_label('Password',exact=True).fill('phase2-local-test-only')
            page.get_by_role('button',name='Sign in',exact=True).last.click()
            page.get_by_role('button',name=re.compile(r'^My Page(?: |$)')).click();page.get_by_role('button',name='My Skeletons',exact=True).click()
            page.get_by_role('button',name='Source analysis · Completed',exact=False).first.click()
            panel=page.get_by_label('New video inputs',exact=True);expect(panel).to_be_visible()
            expect(page.get_by_label('Input reference video',exact=True)).to_be_visible()
            expect(panel).to_contain_text('50 hold candidates')
            page.get_by_text('Wall reference and calibration editor',exact=True).click()
            page.get_by_role('button',name='Save calibration review',exact=True).click()
            expect(panel.get_by_role('alert')).to_be_visible()
            summary=page.request.get('http://127.0.0.1:5177/api/tasks/'+task['id']+'/artifacts/input_summary').json()
            holds=page.request.get('http://127.0.0.1:5177/api/tasks/'+task['id']+'/artifacts/holds').json()
            w,h=summary['width']-1,summary['height']-1;quad=[[0,0],[w,0],[w,h],[0,h]]
            review=dict(reference_frame=summary['reference_frame'],selected_hold_ids=[holds[0]['hold_id']],planes=[dict(id='fixture',polygon=quad,grid_corners=quad,horizontal_steps=1,vertical_steps=1,note='Synthetic browser fixture; not real wall measurement')],notes='TEST ONLY')
            page.get_by_label('Calibration review JSON',exact=True).fill(json.dumps(review))
            page.get_by_role('button',name='Save calibration review',exact=True).click()
            expect(panel).to_contain_text('Calibration review saved')
            expect(panel).to_contain_text('1 / 1 selected holds')
            contacts = page.get_by_label('Contact review', exact=True)
            page.get_by_role('button', name='Load automatic contact candidates', exact=True).click()
            expect(page.get_by_label('Limb 1', exact=True)).to_be_visible()
            # Replace the first candidate's limb, hold, start and release, then remove
            # remaining candidates to avoid introducing accidental overlap.
            while page.get_by_role('button', name='Remove interval 2', exact=True).count():
                page.get_by_role('button', name='Remove interval 2', exact=True).click()
            page.get_by_label('Limb 1', exact=True).select_option('left_foot')
            page.get_by_label('Hold 1', exact=True).select_option(holds[0]['hold_id'])
            page.get_by_label('Start frame 1', exact=True).fill('3')
            page.get_by_label('Release frame 1', exact=True).fill('9')
            page.get_by_label('Contact review notes', exact=True).fill('Synthetic browser correction, not actual motion evidence')
            page.get_by_role('checkbox', name='I reviewed these intervals', exact=False).check()
            page.get_by_role('button', name='Save contact review', exact=True).click()
            expect(contacts).to_contain_text('Contact review saved.')
            saved = page.request.get('http://127.0.0.1:5177/api/tasks/'+task['id']+'/contact-review').json()['saved']
            contact_version = saved['version']
            self.assertEqual(saved['review']['intervals'][0]['limb'], 'left_foot')
            export_url = 'http://127.0.0.1:5177/api/tasks/'+task['id']+'/contact-review/export?version='+contact_version
            exported = page.request.get(export_url).json()
            self.assertEqual([r['frame'] for r in exported['frames'] if r['state']=='hold'], list(range(3,9)))
            self.assertFalse(exported['generation_ready'])
            page.get_by_role('button', name='View contact 1', exact=True).click()
            self.assertAlmostEqual(page.get_by_label('Contact reference video', exact=True).evaluate('(v) => v.currentTime'), 3/summary['fps'], places=2)
            page.get_by_label('Limb 1', exact=True).scroll_into_view_if_needed()
            page.screenshot(path=str(self.output/'input-review-mobile.png'),full_page=True)
            page.reload();page.get_by_role('button',name=re.compile(r'^My Page(?: |$)')).click();page.get_by_role('button',name='My Skeletons',exact=True).click()
            page.get_by_role('button',name='Source analysis · Completed',exact=False).first.click()
            expect(panel).to_contain_text('1 / 1 selected holds')
            expect(page.get_by_label('Limb 1', exact=True)).to_have_value('left_foot')
            expect(page.get_by_label('Release frame 1', exact=True)).to_have_value('9')
            expect(page.get_by_label('Contact review', exact=True)).to_contain_text(contact_version)
            page.get_by_text('Correct or add holds',exact=True).click()
            reference=page.get_by_alt_text('Hold correction reference',exact=True)
            reference.click(position={'x':20,'y':20})
            page.get_by_label('Correction evidence',exact=True).fill('Synthetic UI test, not actual climb evidence')
            page.get_by_label('Hold review notes',exact=True).fill('Missed hold workflow acceptance')
            page.get_by_role('button',name='Save hold corrections',exact=True).click()
            expect(panel).to_contain_text('Hold version saved.')
            hold_doc=page.request.get('http://127.0.0.1:5177/api/tasks/'+task['id']+'/hold-review').json()
            manual_id=hold_doc['review']['corrections'][0]['hold_id']
            expect(page.get_by_label('Hold 1',exact=True).locator('option',has_text=manual_id)).to_have_count(1)
            expect(page.get_by_role('checkbox',name='I reviewed these intervals',exact=False)).not_to_be_checked()
            page.get_by_label('Hold 1',exact=True).select_option(manual_id)
            page.get_by_role('checkbox',name='I reviewed these intervals',exact=False).check()
            page.get_by_role('button',name='Save contact review',exact=True).click()
            expect(contacts).to_contain_text('Contact review saved.')
            updated=page.request.get('http://127.0.0.1:5177/api/tasks/'+task['id']+'/contact-review').json()
            self.assertEqual(updated['saved']['review']['hold_review_version'],hold_doc['version'])
            # Old pinned contact exports survive a newer hold revision.
            self.assertEqual(page.request.get(export_url).status,200)
            page.get_by_text('Wall reference and calibration editor',exact=True).click()
            guide=page.get_by_label('Guided wall calibration',exact=True)
            guide.get_by_label('Angle from horizontal (degrees; blank if unknown)',exact=True).fill('')
            self.assertIsNone(json.loads(page.get_by_label('Calibration review JSON').input_value())['planes'][0]['angle_from_horizontal_deg'])
            page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path=str(self.output/'input-review-desktop.png'),full_page=True)
            browser.close()
        print('Input browser validation:',self.output)
