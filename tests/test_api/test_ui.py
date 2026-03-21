import pytest


class TestLoginPage:
    def test_login_page_renders(self, client):
        response = client.get("/login")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "loginForm" in response.text

    def test_login_page_has_form(self, client):
        response = client.get("/login")
        html = response.text
        assert 'method="POST"' in html
        assert 'action="/auth/login"' in html
        assert 'type="email"' in html
        assert 'type="password"' in html

    def test_login_page_has_error_container(self, client):
        response = client.get("/login")
        assert "loginError" in response.text


class TestPanelPage:
    def test_panel_page_renders(self, client):
        response = client.get("/panel")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_panel_shows_orders_table(self, client):
        response = client.get("/panel")
        html = response.text
        assert "orders-table" in html
        assert "ordersBody" in html

    def test_panel_has_filters(self, client):
        response = client.get("/panel")
        html = response.text
        assert "filterStatus" in html
        assert "filterNotification" in html

    def test_panel_has_pagination(self, client):
        response = client.get("/panel")
        html = response.text
        assert "prevPage" in html
        assert "nextPage" in html

    def test_panel_has_empty_state(self, client):
        response = client.get("/panel")
        assert "emptyState" in response.text
        assert "Sin ordenes" in response.text

    def test_panel_has_loading_state(self, client):
        response = client.get("/panel")
        assert "loadingState" in response.text
        assert "spinner" in response.text

    def test_panel_has_logout(self, client):
        response = client.get("/panel")
        assert "logoutBtn" in response.text
        assert "Cerrar sesion" in response.text

    def test_panel_has_branding(self, client):
        response = client.get("/panel")
        assert "WTA" in response.text
        assert "brand" in response.text


class TestBadges:
    def test_panel_has_badge_classes(self, client):
        response = client.get("/panel")
        html = response.text
        assert "badge-success" in html or "badge-success" in response.text
        assert "badge-warning" in html or "badge-warning" in response.text
        assert "badge-error" in html or "badge-error" in response.text


class TestSettingsPage:
    def test_settings_page_renders(self, client):
        response = client.get("/settings")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_settings_has_template_inputs(self, client):
        response = client.get("/settings")
        html = response.text
        assert "tplInTransit" in html
        assert "tplDelivered" in html

    def test_settings_has_save_button(self, client):
        response = client.get("/settings")
        assert "btnSave" in response.text

    def test_settings_has_system_info(self, client):
        response = client.get("/settings")
        assert "infoWeraha" in response.text
        assert "infoWhatsapp" in response.text


class TestDashboardStats:
    def test_panel_has_stats_grid(self, client):
        response = client.get("/panel")
        assert "stats-grid" in response.text
        assert "statTotal" in response.text
        assert "statNotified" in response.text
        assert "statErrors" in response.text
        assert "statInvalid" in response.text


class TestNavigation:
    def test_panel_has_nav_links(self, client):
        response = client.get("/panel")
        assert "navOrders" in response.text
        assert "navSettings" in response.text

    def test_settings_has_nav_links(self, client):
        response = client.get("/settings")
        assert "navOrders" in response.text
        assert "navSettings" in response.text


class TestStaticAssets:
    def test_css_loads(self, client):
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]
