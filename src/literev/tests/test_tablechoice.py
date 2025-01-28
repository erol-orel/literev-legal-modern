from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase

from literev.libs.select_functions import create_refinement
from literev.libs.table_choice import (
    create_tablechoice_rag_iteration,
    highlight_words,
    highlight_words_topic,
    update_checked_document_page,
    update_new_table_choice,
)
from literev.models import (
    Document,
    Project,
    ProjectRefinement,
    TableChoice,
)


class HighligthKeywords(TestCase):
    def test_highlight_words(self) -> None:
        """Tests highlight words function"""
        sample = """The U.S. highlight national government is a presidential
            federal republic and liberal democracy.
            random tags: <b class="highlight">Senate</b>, Liberal,"""
        expected = """The U.S. <span class="red-highlight">highlight</span> national government is a presidential
            federal republic and <span class="red-highlight">liberal</span> democracy.
            random tags: <b class="highlight">Senate</b>, <span class="red-highlight">Liberal</span>,"""

        words_to_highlight = ["liberal", "senate", "highlight"]
        style_class = "red-highlight"

        result = highlight_words(sample, words_to_highlight, style_class)

        self.assertEqual(expected, result)

    def test_highlight_word_topic(self):
        """Tests highlight words function"""
        sample = "French history is large"
        expected = '<span style="background-color: color-code40">French</span> history is large'
        result = highlight_words_topic(sample, ["french"], "color-code")
        print(result)
        self.assertEqual(expected, result)


class TableSelectCheckButtons(TransactionTestCase):
    def setUp(self):
        """Set up test data Check documents in TableSelect"""
        self.project = Project.objects.create(name="test project")
        self.user = User.objects.create(username="user_test", password="test")
        self.doc_ids = []

        for i in range(20):
            document = Document.objects.create(
                project=self.project,
                raw_document_text=f"content {i}",
            )
            self.doc_ids.append(document.id)

        update_new_table_choice(self.user, self.project, self.doc_ids)

    def test_update_new_table_choice(self):
        """Check if the function creates the expected tablechoices objects"""

        expected = 20
        result = TableChoice.objects.filter(project=self.project).count()

        self.assertEqual(expected, result)

    def test_create_refinement(self):
        refinement_id = create_refinement(
            self.user,
            self.project,
            "test refinement name",
            20,
            "test filter",
        )

        # Check if the refinement exists
        result = ProjectRefinement.objects.filter(id=refinement_id).exists()
        self.assertTrue(result)

    def test_update_checked_document_page(self):
        tablechoice = TableChoice.objects.filter(
            user=self.user, project=self.project
        )

        yes_checked_ids = [int(tc.id) for tc in tablechoice[:3]]
        no_checked_ids = [int(tc.id) for tc in tablechoice[3:6]]
        maybe_checked_ids = [int(tc.id) for tc in tablechoice[6:9]]

        update_checked_document_page(
            self.user,
            self.project,
            yes_checked_ids,
            no_checked_ids,
            maybe_checked_ids,
        )

        expected_count_yes = 3
        expected_count_no = 3
        expected_count_maybe = 14

        result_count_yes = (
            TableChoice.objects.filter(user=self.user, project=self.project)
            .filter(is_check=True)
            .count()
        )
        result_count_no = (
            TableChoice.objects.filter(user=self.user, project=self.project)
            .filter(is_check=False)
            .count()
        )
        result_count_maybe = (
            TableChoice.objects.filter(user=self.user, project=self.project)
            .filter(is_check=None)
            .count()
        )

        self.assertEqual(expected_count_yes, result_count_yes)
        self.assertEqual(expected_count_no, result_count_no)
        self.assertEqual(expected_count_maybe, result_count_maybe)

    def test_create_tablechoice_rag_iteration(self):
        create_tablechoice_rag_iteration(self.user, self.project)

        number_created_tablechoice = TableChoice.objects.filter(
            project=self.project
        ).count()

        self.assertEqual(number_created_tablechoice, 10)
