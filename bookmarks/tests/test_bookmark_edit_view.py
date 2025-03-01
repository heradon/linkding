from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from bookmarks.models import build_tag_string
from bookmarks.tests.helpers import BookmarkFactoryMixin


class BookmarkEditViewTestCase(TestCase, BookmarkFactoryMixin):

    def setUp(self) -> None:
        user = self.get_or_create_test_user()
        self.client.force_login(user)

    def create_form_data(self, overrides=None):
        if overrides is None:
            overrides = {}
        form_data = {
            'url': 'http://example.com/edited',
            'tag_string': 'editedtag1 editedtag2',
            'title': 'edited title',
            'description': 'edited description',
            'unread': False,
            'shared': False,
        }
        return {**form_data, **overrides}

    def test_should_edit_bookmark(self):
        bookmark = self.setup_bookmark()
        form_data = self.create_form_data({'id': bookmark.id})

        self.client.post(reverse('bookmarks:edit', args=[bookmark.id]), form_data)

        bookmark.refresh_from_db()

        self.assertEqual(bookmark.owner, self.user)
        self.assertEqual(bookmark.url, form_data['url'])
        self.assertEqual(bookmark.title, form_data['title'])
        self.assertEqual(bookmark.description, form_data['description'])
        self.assertEqual(bookmark.unread, form_data['unread'])
        self.assertEqual(bookmark.shared, form_data['shared'])
        self.assertEqual(bookmark.tags.count(), 2)
        tags = bookmark.tags.order_by('name').all()
        self.assertEqual(tags[0].name, 'editedtag1')
        self.assertEqual(tags[1].name, 'editedtag2')

    def test_should_edit_unread_state(self):
        bookmark = self.setup_bookmark()

        form_data = self.create_form_data({'id': bookmark.id, 'unread': True})
        self.client.post(reverse('bookmarks:edit', args=[bookmark.id]), form_data)
        bookmark.refresh_from_db()
        self.assertTrue(bookmark.unread)

        form_data = self.create_form_data({'id': bookmark.id, 'unread': False})
        self.client.post(reverse('bookmarks:edit', args=[bookmark.id]), form_data)
        bookmark.refresh_from_db()
        self.assertFalse(bookmark.unread)

    def test_should_edit_shared_state(self):
        bookmark = self.setup_bookmark()

        form_data = self.create_form_data({'id': bookmark.id, 'shared': True})
        self.client.post(reverse('bookmarks:edit', args=[bookmark.id]), form_data)
        bookmark.refresh_from_db()
        self.assertTrue(bookmark.shared)

        form_data = self.create_form_data({'id': bookmark.id, 'shared': False})
        self.client.post(reverse('bookmarks:edit', args=[bookmark.id]), form_data)
        bookmark.refresh_from_db()
        self.assertFalse(bookmark.shared)

    def test_should_prefill_bookmark_form_fields(self):
        tag1 = self.setup_tag()
        tag2 = self.setup_tag()
        bookmark = self.setup_bookmark(tags=[tag1, tag2], title='edited title', description='edited description',
                                       website_title='website title', website_description='website description')

        response = self.client.get(reverse('bookmarks:edit', args=[bookmark.id]))
        html = response.content.decode()

        self.assertInHTML(f'''
            <input type="text" name="url" value="{bookmark.url}" placeholder=" "
                    autofocus class="form-input" required id="id_url">   
        ''', html)

        tag_string = build_tag_string(bookmark.tag_names, ' ')
        self.assertInHTML(f'''
            <input type="text" name="tag_string" value="{tag_string}" 
                    autocomplete="off" autocapitalize="off" class="form-input" id="id_tag_string">
        ''', html)

        self.assertInHTML(f'''
            <input type="text" name="title" value="{bookmark.title}" maxlength="512" autocomplete="off" 
                    class="form-input" id="id_title">
        ''', html)

        self.assertInHTML(f'''
            <textarea name="description" cols="40" rows="2" class="form-input" id="id_description">
                {bookmark.description}
            </textarea>
        ''', html)

        self.assertInHTML(f'''
            <input type="hidden" name="website_title"  id="id_website_title"
                    value="{bookmark.website_title}">
        ''', html)

        self.assertInHTML(f'''
            <input type="hidden" name="website_description"  id="id_website_description"
                    value="{bookmark.website_description}">
        ''', html)

    def test_should_redirect_to_return_url(self):
        bookmark = self.setup_bookmark()
        form_data = self.create_form_data()

        url = reverse('bookmarks:edit', args=[bookmark.id]) + '?return_url=' + reverse('bookmarks:close')
        response = self.client.post(url, form_data)

        self.assertRedirects(response, reverse('bookmarks:close'))

    def test_should_redirect_to_bookmark_index_by_default(self):
        bookmark = self.setup_bookmark()
        form_data = self.create_form_data()

        response = self.client.post(reverse('bookmarks:edit', args=[bookmark.id]), form_data)

        self.assertRedirects(response, reverse('bookmarks:index'))

    def test_should_not_redirect_to_external_url(self):
        bookmark = self.setup_bookmark()

        def post_with(return_url, follow=None):
            form_data = self.create_form_data()
            url = reverse('bookmarks:edit', args=[bookmark.id]) + f'?return_url={return_url}'
            return self.client.post(url, form_data, follow=follow)

        response = post_with('https://example.com')
        self.assertRedirects(response, reverse('bookmarks:index'))
        response = post_with('//example.com')
        self.assertRedirects(response, reverse('bookmarks:index'))
        response = post_with('://example.com')
        self.assertRedirects(response, reverse('bookmarks:index'))

        response = post_with('/foo//example.com', follow=True)
        self.assertEqual(response.status_code, 404)

    def test_can_only_edit_own_bookmarks(self):
        other_user = User.objects.create_user('otheruser', 'otheruser@example.com', 'password123')
        bookmark = self.setup_bookmark(user=other_user)
        form_data = self.create_form_data({'id': bookmark.id})

        response = self.client.post(reverse('bookmarks:edit', args=[bookmark.id]), form_data)
        bookmark.refresh_from_db()
        self.assertNotEqual(bookmark.url, form_data['url'])
        self.assertEqual(response.status_code, 404)

    def test_should_respect_share_profile_setting(self):
        bookmark = self.setup_bookmark()

        self.user.profile.enable_sharing = False
        self.user.profile.save()
        response = self.client.get(reverse('bookmarks:edit', args=[bookmark.id]))
        html = response.content.decode()

        self.assertInHTML('''
            <label for="id_shared" class="form-checkbox">
              <input type="checkbox" name="shared" id="id_shared">
              <i class="form-icon"></i>
              <span>Share</span>
            </label>            
        ''', html, count=0)

        self.user.profile.enable_sharing = True
        self.user.profile.save()
        response = self.client.get(reverse('bookmarks:edit', args=[bookmark.id]))
        html = response.content.decode()

        self.assertInHTML('''
            <label for="id_shared" class="form-checkbox">
              <input type="checkbox" name="shared" id="id_shared">
              <i class="form-icon"></i>
              <span>Share</span>
            </label>            
        ''', html, count=1)
