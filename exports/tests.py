import io
import json
import zipfile
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from notes.models import Note, Notebook, Tag


class ExportNotesTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Usuário dono das notas
        self.user = User.objects.create_user(
            email='alice@exemplo.com',
            password='Password123!',
            full_name='Alice Silva'
        )

        # Outro usuário para testes de isolamento de dados
        self.other_user = User.objects.create_user(
            email='bob@exemplo.com',
            password='Password123!',
            full_name='Bob Santos'
        )

        # Caderno e Nota de Alice
        self.notebook = Notebook.objects.create(
            user=self.user,
            title='Projetos 2026'
        )
        self.tag = Tag.objects.create(
            user=self.user,
            name='urgente'
        )
        self.note = Note.objects.create(
            user=self.user,
            notebook=self.notebook,
            title='Lançamento do skdnote',
            content_plain='# Planejamento de Lançamento\n\n- Testar checkout\n- Verificar SEO',
            content_html='<h1>Planejamento de Lançamento</h1><ul><li>Testar checkout</li><li>Verificar SEO</li></ul>'
        )
        self.note.tags.add(self.tag)

    def test_unauthenticated_export_redirects_to_login(self):
        """Usuário não logado é redirecionado ao tentar exportar notas ou backup."""
        url_md = reverse('exports:note_markdown', kwargs={'note_id': self.note.id})
        response = self.client.get(url_md)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

        url_zip = reverse('exports:backup_zip')
        response_zip = self.client.get(url_zip)
        self.assertEqual(response_zip.status_code, 302)

    def test_export_single_note_markdown(self):
        """Verifica a exportação de uma nota para o formato Markdown (.md)."""
        self.client.force_login(self.user)
        url = reverse('exports:note_markdown', kwargs={'note_id': self.note.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/markdown', response['Content-Type'])
        self.assertIn('attachment; filename="lancamento-do-skdnote.md"', response['Content-Disposition'])

        content = response.content.decode('utf-8')
        self.assertIn('# Lançamento do skdnote', content)
        self.assertIn('Projetos 2026', content)
        self.assertIn('urgente', content)
        self.assertIn('- Testar checkout', content)

    def test_export_single_note_html_view_and_download(self):
        """Verifica visualização de impressão e download do arquivo HTML."""
        self.client.force_login(self.user)
        url = reverse('exports:note_html', kwargs={'note_id': self.note.id})

        # 1. Modo visualização de impressão (abre no navegador)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])
        self.assertContains(response, 'Lançamento do skdnote')
        self.assertContains(response, 'Imprimir / Salvar em PDF')

        # 2. Modo download direto (?download=1)
        response_dl = self.client.get(url + '?download=1')
        self.assertEqual(response_dl.status_code, 200)
        self.assertIn('attachment; filename="lancamento-do-skdnote.html"', response_dl['Content-Disposition'])

    def test_other_user_cannot_export_private_note(self):
        """Outro usuário não pode exportar uma nota que não pertence a ele (HTTP 404)."""
        self.client.force_login(self.other_user)
        url = reverse('exports:note_markdown', kwargs={'note_id': self.note.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_full_vault_backup_zip_structure(self):
        """Verifica a geração do arquivo ZIP com manifest.json e notas em pastas."""
        # Cria uma nota solta (sem caderno)
        Note.objects.create(
            user=self.user,
            title='Ideia Avulsa',
            content_plain='Criar atalhos de teclado.'
        )

        self.client.force_login(self.user)
        url = reverse('exports:backup_zip')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/zip', response['Content-Type'])
        self.assertIn('attachment; filename="skdnote-backup-', response['Content-Disposition'])

        # Analisa o arquivo ZIP gerado em memória
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            namelist = zf.namelist()

            # 1. Verifica presença do manifest.json
            self.assertIn('manifest.json', namelist)
            manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
            self.assertEqual(manifest['app'], 'skdnote')
            self.assertEqual(manifest['user_email'], 'alice@exemplo.com')
            self.assertEqual(manifest['total_notes'], 2)

            # 2. Verifica estrutura de diretórios dos cadernos
            self.assertIn('Projetos 2026/Lancamento do skdnote.md', [n.replace('ç', 'c') for n in namelist] or namelist)
            self.assertIn('Sem Caderno/Ideia Avulsa.md', namelist)

            # 3. Lê conteúdo do arquivo markdown no ZIP
            matched_note = [n for n in namelist if 'Lancamento' in n or 'Lançamento' in n][0]
            md_content = zf.read(matched_note).decode('utf-8')
            self.assertIn('# Lançamento do skdnote', md_content)

    def test_export_single_note_pdf(self):
        """Verifica a exportação de uma nota para o formato PDF (.pdf)."""
        self.client.force_login(self.user)
        url = reverse('exports:note_pdf', kwargs={'note_id': self.note.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="lancamento-do-skdnote.pdf"', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreater(len(response.content), 500)

    def test_export_single_note_docx(self):
        """Verifica a exportação de uma nota para o formato Microsoft Word (.docx)."""
        self.client.force_login(self.user)
        url = reverse('exports:note_docx', kwargs={'note_id': self.note.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        self.assertIn('attachment; filename="lancamento-do-skdnote.docx"', response['Content-Disposition'])
        # DOCX é um contêiner zip, portanto começa com a assinatura PK (b'PK\x03\x04')
        self.assertTrue(response.content.startswith(b'PK'))
        self.assertGreater(len(response.content), 1000)

    def test_user_cannot_export_other_user_note_pdf_or_docx(self):
        """Um usuário não pode exportar notas de outro usuário em PDF ou DOCX."""
        self.client.force_login(self.other_user)
        url_pdf = reverse('exports:note_pdf', kwargs={'note_id': self.note.id})
        res_pdf = self.client.get(url_pdf)
        self.assertEqual(res_pdf.status_code, 404)

        url_docx = reverse('exports:note_docx', kwargs={'note_id': self.note.id})
        res_docx = self.client.get(url_docx)
        self.assertEqual(res_docx.status_code, 404)
