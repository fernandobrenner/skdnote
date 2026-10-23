import json
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Currency
from notes.models import Note, Notebook, Tag
from notes.services import get_user_notes_quota, user_can_create_note


class NotesDomainAndEditorTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='autor@exemplo.com',
            password='Password123!',
            full_name='Autor das Notas',
            preferred_currency=Currency.BRL
        )
        self.client.force_login(self.user)

    def test_create_note_and_app_view(self):
        """Verifica criação de nova anotação e carregamento da interface UpNote."""
        response = self.client.post(reverse('notes:note_create'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Note.objects.filter(user=self.user).count(), 1)
        note = Note.objects.filter(user=self.user).first()
        self.assertEqual(note.title, "Sem título")

        # Verifica carregamento do app
        app_response = self.client.get(reverse('notes:app') + f'?note_id={note.id}')
        self.assertEqual(app_response.status_code, 200)
        self.assertContains(app_response, "Sem título")

    def test_autosave_updates_content_and_title(self):
        """Verifica se o endpoint de autosave atualiza título, HTML e texto puro via JSON."""
        note = Note.objects.create(user=self.user, title="Rascunho Inicial")

        response = self.client.post(
            reverse('notes:note_autosave', kwargs={'note_id': note.id}),
            data=json.dumps({
                'title': 'Plano Estratégico skdnote',
                'content_html': '<p>Primeiro parágrafo de anotações.</p>',
                'content_plain': 'Primeiro parágrafo de anotações.'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'saved')
        self.assertEqual(data['title'], 'Plano Estratégico skdnote')

        note.refresh_from_db()
        self.assertEqual(note.title, 'Plano Estratégico skdnote')
        self.assertEqual(note.content_plain, 'Primeiro parágrafo de anotações.')

    def test_autosave_infers_title_from_first_line_if_empty(self):
        """Verifica se o autosave infere o título da primeira linha caso o campo esteja vazio."""
        note = Note.objects.create(user=self.user, title="")

        response = self.client.post(
            reverse('notes:note_autosave', kwargs={'note_id': note.id}),
            data=json.dumps({
                'title': '',
                'content_html': '<p>Ideia brilhante para o projeto</p>',
                'content_plain': 'Ideia brilhante para o projeto\nLinha dois.'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.title, 'Ideia brilhante para o projeto')

    def test_pin_and_favorite_toggles(self):
        """Verifica alternância de notas fixadas e favoritas."""
        note = Note.objects.create(user=self.user, title="Nota Importante")

        # Fixar
        self.client.post(reverse('notes:note_toggle_pin', kwargs={'note_id': note.id}))
        note.refresh_from_db()
        self.assertTrue(note.is_pinned)

        # Favoritar
        self.client.post(reverse('notes:note_toggle_favorite', kwargs={'note_id': note.id}))
        note.refresh_from_db()
        self.assertTrue(note.is_favorite)

    def test_soft_delete_and_restore(self):
        """Verifica envio para a lixeira (soft delete) e posterior restauração."""
        note = Note.objects.create(user=self.user, title="Nota para Deletar")

        # Mover para a Lixeira
        self.client.post(reverse('notes:note_move_to_trash', kwargs={'note_id': note.id}))
        note.refresh_from_db()
        self.assertTrue(note.is_deleted)
        self.assertIsNotNone(note.deleted_at)

        # Restaurar
        self.client.post(reverse('notes:note_restore', kwargs={'note_id': note.id}))
        note.refresh_from_db()
        self.assertFalse(note.is_deleted)
        self.assertIsNone(note.deleted_at)

    def test_permanent_deletion(self):
        """Verifica exclusão permanente de uma nota."""
        note = Note.objects.create(user=self.user, title="Exclusão Permanente", is_deleted=True)
        self.client.post(reverse('notes:note_delete_permanent', kwargs={'note_id': note.id}))
        self.assertFalse(Note.objects.filter(id=note.id).exists())

    def test_free_plan_quota_enforcement_at_50_notes(self):
        """Verifica a regra de negócio: bloqueio da 51ª nota no plano gratuito."""
        # Cria 50 notas ativas
        notes = [Note(user=self.user, title=f"Nota {i}") for i in range(50)]
        Note.objects.bulk_create(notes)

        quota = get_user_notes_quota(self.user)
        self.assertEqual(quota['current_notes'], 50)
        self.assertFalse(quota['can_create'])
        self.assertFalse(user_can_create_note(self.user))

        # Tentativa de criar a 51ª nota via AJAX retorna HTTP 402 (Payment Required / Paywall)
        response_ajax = self.client.post(
            reverse('notes:note_create'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response_ajax.status_code, 402)
        self.assertEqual(response_ajax.json()['status'], 'quota_exceeded')

        # Tentativa de criar a 51ª nota via requisição padrão redireciona para paywall
        response_regular = self.client.post(reverse('notes:note_create'))
        self.assertEqual(response_regular.status_code, 302)
        self.assertIn('paywall=1', response_regular.url)

    def test_notebooks_and_subnotebooks_creation(self):
        """Verifica criação de cadernos e subcadernos aninhados."""
        # Caderno Raiz
        self.client.post(reverse('notes:notebook_create'), {
            'title': 'Projetos de Software',
            'icon': '💻'
        })
        root_nb = Notebook.objects.get(user=self.user, title='Projetos de Software')
        self.assertFalse(root_nb.is_subnotebook)

        # Subcaderno
        self.client.post(reverse('notes:notebook_create'), {
            'title': 'skdnote MVP',
            'icon': '🚀',
            'parent_id': str(root_nb.id)
        })
        sub_nb = Notebook.objects.get(user=self.user, title='skdnote MVP')
        self.assertTrue(sub_nb.is_subnotebook)
        self.assertEqual(sub_nb.parent, root_nb)

    def test_tag_creation(self):
        """Verifica criação de etiquetas."""
        self.client.post(reverse('notes:tag_create'), {
            'name': 'prioridade',
            'color': '#ef4444'
        })
        self.assertTrue(Tag.objects.filter(user=self.user, name='prioridade').exists())

    def test_toggle_note_sharing_enable_and_disable(self):
        """Verifica habilitação e desativação de compartilhamento por link seguro."""
        note = Note.objects.create(
            user=self.user,
            title='Artigo Público',
            content_html='<p>Conteúdo de leitura pública.</p>'
        )

        # 1. Habilita compartilhamento
        res_enable = self.client.post(
            reverse('notes:note_toggle_share', kwargs={'note_id': note.id}),
            {'action': 'enable'}
        )
        self.assertEqual(res_enable.status_code, 200)
        data_enable = res_enable.json()
        self.assertTrue(data_enable['is_shared'])
        self.assertTrue(bool(data_enable['token']))
        self.assertIn('/share/', data_enable['share_url'])

        note.refresh_from_db()
        self.assertTrue(note.is_shared)
        self.assertIsNotNone(note.share_token)

        # 2. Desativa compartilhamento
        res_disable = self.client.post(
            reverse('notes:note_toggle_share', kwargs={'note_id': note.id}),
            {'action': 'disable'}
        )
        self.assertEqual(res_disable.status_code, 200)
        data_disable = res_disable.json()
        self.assertFalse(data_disable['is_shared'])

        note.refresh_from_db()
        self.assertFalse(note.is_shared)

    def test_shared_note_public_access(self):
        """Verifica acesso público desautenticado a uma nota compartilhada."""
        note = Note.objects.create(
            user=self.user,
            title='Guia Aberto',
            content_html='<p>Bem-vindo ao guia aberto do skdnote.</p>'
        )
        token = note.enable_sharing()

        # Cliente desautenticado (anônimo)
        anon_client = Client()
        url = reverse('shared_note_root', kwargs={'share_token': token})
        response = anon_client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Guia Aberto')
        self.assertContains(response, 'Bem-vindo ao guia aberto do skdnote.')
        self.assertContains(response, 'Criar Anotações Grátis')

        # Se compartilhamento for desativado, retorna 404
        note.disable_sharing()
        res_disabled = anon_client.get(url)
        self.assertEqual(res_disabled.status_code, 404)

        # Se nota for movida para lixeira, mesmo com is_shared=True, retorna 404
        note.enable_sharing()
        note.move_to_trash()
        res_trash = anon_client.get(url)
        self.assertEqual(res_trash.status_code, 404)

    def test_other_user_cannot_toggle_share_of_another_user_note(self):
        """Outro usuário não pode alterar o compartilhamento de nota alheia."""
        other_user = User.objects.create_user(
            email='intruso@exemplo.com',
            password='Password123!'
        )
        note = Note.objects.create(user=self.user, title='Segredo')

        self.client.force_login(other_user)
        response = self.client.post(
            reverse('notes:note_toggle_share', kwargs={'note_id': note.id}),
            {'action': 'enable'}
        )
        self.assertEqual(response.status_code, 404)


class CrossUserNoteIsolationSecurityTests(TestCase):
    """
    Suíte de testes de segurança estrita:
    Garante isolamento absoluto de dados entre usuários diferentes (Multi-Tenant).
    """
    def setUp(self):
        self.client = Client()
        # Usuário A (Dono dos dados privados)
        self.user_a = User.objects.create_user(
            email='alice@empresa.com',
            password='Password123!',
            full_name='Alice Silva'
        )
        self.notebook_a = Notebook.objects.create(user=self.user_a, title='Caderno Privado Alice')
        self.tag_a = Tag.objects.create(user=self.user_a, name='confidencial')
        self.note_a = Note.objects.create(
            user=self.user_a,
            notebook=self.notebook_a,
            title='Senhas e Chaves Secretas da Alice',
            content_plain='Chave-API-Super-Secreta-12345',
            content_html='<p>Chave-API-Super-Secreta-12345</p>'
        )
        self.note_a.tags.add(self.tag_a)

        # Usuário B (Outro usuário comum / possível intruso)
        self.user_b = User.objects.create_user(
            email='bob@empresa.com',
            password='Password123!',
            full_name='Bob Santos'
        )
        self.note_b = Note.objects.create(
            user=self.user_b,
            title='Lista de Tarefas do Bob',
            content_plain='Comprar café e revisar código.'
        )

    def test_user_cannot_view_another_users_note_in_app(self):
        """Usuário B não visualiza notas de Usuário A ao forçar ?note_id= no app."""
        self.client.force_login(self.user_b)
        response = self.client.get(reverse('notes:app') + f'?note_id={self.note_a.id}')
        self.assertEqual(response.status_code, 200)

        # O conteúdo confidencial da Alice NÃO deve estar presente no HTML
        self.assertNotContains(response, 'Senhas e Chaves Secretas da Alice')
        self.assertNotContains(response, 'Chave-API-Super-Secreta-12345')
        self.assertNotContains(response, 'Caderno Privado Alice')

        # O usuário B vê apenas a sua própria nota
        self.assertContains(response, 'Lista de Tarefas do Bob')

    def test_user_cannot_autosave_another_users_note(self):
        """Usuário B é bloqueado com 404 ao tentar alterar nota da Alice via autosave."""
        self.client.force_login(self.user_b)
        url = reverse('notes:note_autosave', kwargs={'note_id': self.note_a.id})
        payload = json.dumps({'title': 'Hackeado', 'content_plain': 'Conteudo adulterado'})

        response = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 404)

        # Conteúdo da nota original da Alice permanece intacto no banco de dados
        self.note_a.refresh_from_db()
        self.assertEqual(self.note_a.title, 'Senhas e Chaves Secretas da Alice')
        self.assertEqual(self.note_a.content_plain, 'Chave-API-Super-Secreta-12345')

    def test_user_cannot_modify_lifecycle_of_another_users_note(self):
        """Usuário B recebe 404 ao tentar fixar, favoritar, mover para lixeira, restaurar ou excluir nota de A."""
        self.client.force_login(self.user_b)

        # Fixar
        self.assertEqual(self.client.post(reverse('notes:note_toggle_pin', kwargs={'note_id': self.note_a.id})).status_code, 404)
        # Favoritar
        self.assertEqual(self.client.post(reverse('notes:note_toggle_favorite', kwargs={'note_id': self.note_a.id})).status_code, 404)
        # Mover para Lixeira
        self.assertEqual(self.client.post(reverse('notes:note_move_to_trash', kwargs={'note_id': self.note_a.id})).status_code, 404)
        # Restaurar
        self.assertEqual(self.client.post(reverse('notes:note_restore', kwargs={'note_id': self.note_a.id})).status_code, 404)
        # Excluir Definitivamente
        self.assertEqual(self.client.post(reverse('notes:note_delete_permanent', kwargs={'note_id': self.note_a.id})).status_code, 404)

        # Nota de Alice não foi excluída nem alterada
        self.note_a.refresh_from_db()
        self.assertFalse(self.note_a.is_deleted)
        self.assertFalse(self.note_a.is_pinned)

    def test_user_cannot_export_another_users_note(self):
        """Usuário B recebe 404 ao tentar exportar nota de Alice em PDF, DOCX, MD ou HTML."""
        self.client.force_login(self.user_b)

        self.assertEqual(self.client.get(reverse('exports:note_markdown', kwargs={'note_id': self.note_a.id})).status_code, 404)
        self.assertEqual(self.client.get(reverse('exports:note_html', kwargs={'note_id': self.note_a.id})).status_code, 404)
        self.assertEqual(self.client.get(reverse('exports:note_pdf', kwargs={'note_id': self.note_a.id})).status_code, 404)
        self.assertEqual(self.client.get(reverse('exports:note_docx', kwargs={'note_id': self.note_a.id})).status_code, 404)

    def test_user_cannot_delete_another_users_notebook_or_tag(self):
        """Usuário B recebe 404 ao tentar excluir cadernos ou etiquetas de Alice."""
        self.client.force_login(self.user_b)

        # Caderno
        self.assertEqual(self.client.post(reverse('notes:notebook_delete', kwargs={'notebook_id': self.notebook_a.id})).status_code, 404)
        self.assertTrue(Notebook.objects.filter(id=self.notebook_a.id).exists())

        # Tag
        self.assertEqual(self.client.post(reverse('notes:tag_delete', kwargs={'tag_id': self.tag_a.id})).status_code, 404)
        self.assertTrue(Tag.objects.filter(id=self.tag_a.id).exists())

    def test_backup_zip_contains_only_authenticated_users_notes(self):
        """Backup ZIP gerado por Bob não contém absolutamente nenhum dado de Alice."""
        import zipfile
        import io

        self.client.force_login(self.user_b)
        response = self.client.get(reverse('exports:backup_zip'))
        self.assertEqual(response.status_code, 200)

        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_names = zf.namelist()
            manifest_content = zf.read('manifest.json').decode('utf-8')

            # O manifest deve conter o e-mail de Bob e apenas suas notas
            self.assertIn('bob@empresa.com', manifest_content)
            self.assertNotIn('alice@empresa.com', manifest_content)
            self.assertNotIn('Senhas e Chaves Secretas da Alice', manifest_content)
            self.assertNotIn('Chave-API-Super-Secreta-12345', manifest_content)

