import unittest
import json
import io
import os
from app import app, db
from models import User, Project, Document, Decision, Task, Risk, HandoverReport, Acknowledgement

class KnowBridgeTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def register_and_login(self, username='testlead', email='lead@knowbridge.ai', password='password123', full_name='Dr. Alex Rivera', role='admin'):
        # Register
        res = self.client.post('/api/auth/register', data=json.dumps({
            'username': username,
            'email': email,
            'password': password,
            'full_name': full_name,
            'role': role
        }), content_type='application/json')
        self.assertIn(res.status_code, [200, 201])

        # Login
        res_login = self.client.post('/api/auth/login', data=json.dumps({
            'username': username,
            'password': password
        }), content_type='application/json')
        self.assertEqual(res_login.status_code, 200)
        return json.loads(res_login.data)

    def test_complete_handover_flow(self):
        # 1. Register & Login
        user_info = self.register_and_login()
        self.assertIn('user', user_info)
        user_id = user_info['user']['id']

        # 2. Create Project
        res = self.client.post('/api/projects', data=json.dumps({
            'name': 'Autonomous Drone Nav Platform',
            'description': 'Handover of flight path telemetry and obstacle avoidance systems.'
        }), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        project_data = json.loads(res.data)
        project_id = project_data['project']['id']
        self.assertEqual(project_data['project']['name'], 'Autonomous Drone Nav Platform')

        # 3. Upload Project Document
        sample_doc_content = (
            "PROJECT STATUS & HANDOVER SPECIFICATION\n"
            "Date: 2026-11-01\n"
            "Lead: Dr. Alex Rivera\n\n"
            "Important Decisions:\n"
            "We decided to migrate the communication protocol from WebSockets to gRPC for real-time telemetry streaming.\n"
            "Architectural decision approved by Alex Rivera on October 15.\n\n"
            "Pending Tasks:\n"
            "Action item: Elena Gomez must complete unit tests for the collision avoidance Kalman filter by November 20.\n"
            "Need to implement secure certificate rotation for edge gateway by December 1.\n\n"
            "Identified Project Risks:\n"
            "Major risk: Battery overheating during high-torque crosswind maneuvers has caused telemetry dropouts.\n"
            "Potential blocker: Vendor delay for thermal sensors may delay flight testing by 3 weeks.\n\n"
            "Dependencies:\n"
            "Navigation stack depends on sensor calibration suite.\n"
            "Flight controller requires hardware firmware version 2.4.1.\n"
        )

        data = {
            'file': (io.BytesIO(sample_doc_content.encode('utf-8')), 'handover_notes.txt')
        }
        res_upload = self.client.post(f'/api/projects/{project_id}/documents', data=data, content_type='multipart/form-data')
        self.assertIn(res_upload.status_code, [200, 201])

        # Verify Document in list
        res_docs = self.client.get(f'/api/projects/{project_id}/documents')
        self.assertEqual(res_docs.status_code, 200)
        docs = json.loads(res_docs.data)['documents']
        self.assertEqual(len(docs), 1)
        doc_id = docs[0]['id']

        # 4. Trigger AI Extraction (uses keyword/regex local fallback when no API key is supplied)
        res_process = self.client.post(f'/api/documents/{doc_id}/process', content_type='application/json')
        self.assertEqual(res_process.status_code, 200)
        ai_res = json.loads(res_process.data)
        results = ai_res.get('results', ai_res)
        self.assertTrue(len(results.get('decisions', [])) > 0 or len(results.get('tasks', [])) > 0 or len(results.get('risks', [])) > 0)

        # 5. Verify and Review Decision
        res_dec = self.client.get(f'/api/projects/{project_id}/decisions')
        self.assertEqual(res_dec.status_code, 200)
        decisions = json.loads(res_dec.data)['decisions']
        if decisions:
            dec_id = decisions[0]['id']
            res_rev = self.client.post(f'/api/decisions/{dec_id}/review', data=json.dumps({
                'action': 'approved',
                'comment': 'Validated against system architecture design'
            }), content_type='application/json')
            self.assertEqual(res_rev.status_code, 200)

        # 6. Add Manual Task & Review
        res_task = self.client.post(f'/api/projects/{project_id}/tasks', data=json.dumps({
            'title': 'Sign off compliance checklist with FAA',
            'description': 'Final legal handover signoff before transfer',
            'assigned_to': 'Jordan Blake',
            'priority': 'high',
            'status': 'in_progress',
            'deadline': '2026-11-30'
        }), content_type='application/json')
        self.assertEqual(res_task.status_code, 201)

        # 7. Generate Handover Report (ReportLab PDF)
        res_gen = self.client.post(f'/api/projects/{project_id}/reports/generate', content_type='application/json')
        self.assertEqual(res_gen.status_code, 201)
        gen_data = json.loads(res_gen.data)
        report_id = gen_data['report']['id']

        # 8. Download PDF Report
        res_pdf = self.client.get(f'/api/reports/{report_id}/download')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.mimetype, 'application/pdf')
        self.assertTrue(len(res_pdf.data) > 1000)

        # 9. Download CSV Report
        res_csv = self.client.get(f'/api/reports/{report_id}/download/csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, 'text/csv')
        self.assertIn(b'--- DECISIONS ---', res_csv.data)

        # 10. Acknowledge Handover Report
        res_ack = self.client.post(f'/api/reports/{report_id}/acknowledge', content_type='application/json')
        self.assertEqual(res_ack.status_code, 200)

        # 11. Dashboard Stats
        res_stats = self.client.get('/api/dashboard/stats')
        self.assertEqual(res_stats.status_code, 200)
        data = json.loads(res_stats.data)
        stats = data.get('stats', data)
        self.assertGreaterEqual(stats.get('total_projects', 0), 1)

        print("\nAll 11 Core End-to-End Handover Verification Steps Passed Successfully!")

if __name__ == '__main__':
    unittest.main()
