from django.test import Client, TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from systemapp.models import NoteContent, NoteDocument, NoteRemark, NoteSheet, ProcurementQuotation
from userapp.models import RoleMaster, User


class NoteSheetWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.role = RoleMaster.objects.create(role_name="Officer")
        self.sender = User.objects.create(
            login_id="sender",
            password="pass1234",
            role=self.role,
            officer_name="Sender Officer",
            designation="Section Officer",
        )
        self.receiver = User.objects.create(
            login_id="receiver",
            password="pass1234",
            role=self.role,
            officer_name="Receiver Officer",
            designation="Deputy Director",
        )
        self.director = User.objects.create(
            login_id="director",
            password="pass1234",
            role=self.role,
            officer_name="Director Officer",
            designation="Director",
        )
        self.chairman = User.objects.create(
            login_id="chairman",
            password="pass1234",
            role=self.role,
            officer_name="Chairman Officer",
            designation="Chairman",
        )
        self.finance = User.objects.create(
            login_id="finance",
            password="pass1234",
            role=self.role,
            officer_name="Finance Officer",
            designation="Finance",
        )
        self.note = NoteSheet.objects.create(
            title="Budget approval",
            description="Initial draft",
            created_by=self.sender,
        )

    def login_session(self, user):
        session = self.client.session
        session["user_id"] = user.id
        session["officer_name"] = user.officer_name
        session["role"] = user.role.role_name
        session.save()

    def test_sender_sees_forwarded_file_in_sent_register(self):
        self.note.forwarded_to = self.receiver
        self.note.save()
        NoteRemark.objects.create(
            notesheet=self.note,
            action="FORWARDED",
            remark_text="Please review the budget note.",
            created_by=self.sender,
            forwarded_to=self.receiver,
        )

        self.login_session(self.sender)
        response = self.client.get(reverse("sent_notes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.note.notesheet_no)

    def test_forwarded_file_becomes_read_only_for_sender(self):
        self.note.forwarded_to = self.receiver
        self.note.save()
        NoteRemark.objects.create(
            notesheet=self.note,
            action="FORWARDED",
            remark_text="Forwarded for review",
            created_by=self.sender,
            forwarded_to=self.receiver,
        )

        self.login_session(self.sender)
        response = self.client.get(reverse("edit_notesheet", args=[self.note.id]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_edit"])
        self.assertContains(response, "Read-only")

    def test_save_note_entry_creates_shared_timeline_comment(self):
        self.login_session(self.sender)
        response = self.client.post(
            reverse("edit_notesheet", args=[self.note.id]),
            {"action_type": "save", "content": "Finance concurrence is required."},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(NoteContent.objects.filter(notesheet=self.note).exists())
        self.assertTrue(
            NoteRemark.objects.filter(
                notesheet=self.note,
                action="COMMENT",
                remark_text="Finance concurrence is required.",
                created_by=self.sender,
            ).exists()
        )

    def test_receiver_gets_note_in_inbox_after_forward(self):
        self.note.forwarded_to = self.receiver
        self.note.save()
        NoteRemark.objects.create(
            notesheet=self.note,
            action="FORWARDED",
            remark_text="For your action.",
            created_by=self.sender,
            forwarded_to=self.receiver,
        )

        self.login_session(self.receiver)
        response = self.client.get(reverse("inbox"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.note.notesheet_no)

    def test_remark_attachment_is_saved_with_timeline_entry(self):
        self.login_session(self.sender)
        attachment = SimpleUploadedFile(
            "support.pdf",
            b"%PDF-1.4 test attachment",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("edit_notesheet", args=[self.note.id]),
            {
                "action_type": "save",
                "content": "<p>Attached supporting paper.</p>",
                "remark_attachment": attachment,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            NoteRemark.objects.filter(
                notesheet=self.note,
                action="COMMENT",
                created_by=self.sender,
            ).exclude(attachment="").exists()
        )

    def test_create_notesheet_description_does_not_create_timeline_entry(self):
        self.login_session(self.sender)

        response = self.client.post(
            reverse("create_notesheet"),
            {
                "title": "Procurement note",
                "description": "This should stay only in the top summary.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        created_note = NoteSheet.objects.get(title="Procurement note")
        self.assertEqual(created_note.description, "This should stay only in the top summary.")
        self.assertFalse(NoteRemark.objects.filter(notesheet=created_note).exists())
        self.assertFalse(NoteContent.objects.filter(notesheet=created_note).exists())

    def test_legacy_description_comment_is_hidden_from_timeline(self):
        NoteRemark.objects.create(
            notesheet=self.note,
            action="COMMENT",
            remark_text=self.note.description,
            created_by=self.sender,
        )

        self.login_session(self.sender)
        response = self.client.get(reverse("edit_notesheet", args=[self.note.id]))

        self.assertEqual(response.status_code, 200)
        timeline = list(response.context["timeline"])
        self.assertEqual(len(timeline), 0)

    def test_legacy_uploaded_file_is_shown_in_same_timeline(self):
        NoteDocument.objects.create(
            notesheet=self.note,
            file=SimpleUploadedFile(
                "legacy.pdf",
                b"%PDF-1.4 legacy file",
                content_type="application/pdf",
            ),
        )

        self.login_session(self.sender)
        response = self.client.get(reverse("edit_notesheet", args=[self.note.id]))

        self.assertEqual(response.status_code, 200)
        timeline = list(response.context["timeline"])
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["event_type"], "document")

    def test_creator_can_start_quotation_workflow(self):
        self.login_session(self.sender)
        response = self.client.post(
            reverse("Quation_file", args=[self.note.id]),
            {"action_type": "start_quotation"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.procurement_status, "PENDING_DIRECTOR")
        self.assertEqual(self.note.forwarded_to_id, self.director.id)

    def test_l1_calculation_marks_lowest_vendor(self):
        self.note.procurement_status = "QUOTATIONS_UPLOAD"
        self.note.forwarded_to = self.sender
        self.note.save()
        ProcurementQuotation.objects.create(
            notesheet=self.note,
            vendor_name="Vendor A",
            amount="5000.00",
            uploaded_by=self.sender,
        )
        ProcurementQuotation.objects.create(
            notesheet=self.note,
            vendor_name="Vendor B",
            amount="4200.00",
            uploaded_by=self.sender,
        )

        self.login_session(self.sender)
        response = self.client.post(
            reverse("Quation_file", args=[self.note.id]),
            {"action_type": "calculate_l1"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.procurement_status, "PENDING_L1_APPROVAL")
        self.assertEqual(self.note.quotations.get(is_l1=True).vendor_name, "Vendor B")
