class TestLoginPage:
    def test_login_page_renders(self, client):
        response = client.get("/login")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "loginForm" in response.text

    def test_login_page_has_tiendanube_help_link(self, client):
        response = client.get("/login")
        assert "/ayuda/conectar-tiendanube" in response.text

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

    def test_login_page_has_register_link(self, client):
        response = client.get("/login")
        assert "/register" in response.text


class TestRegisterPage:
    def test_register_page_renders(self, client):
        response = client.get("/register")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "registerForm" in response.text

    def test_register_page_has_fields(self, client):
        response = client.get("/register")
        html = response.text
        assert 'action="/auth/register"' in html
        assert 'id="storeName"' in html
        assert 'type="email"' in html
        assert 'type="password"' in html


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

    def test_panel_footer_has_public_help_link(self, client):
        response = client.get("/panel")
        assert "/ayuda/conectar-tiendanube" in response.text


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
        assert "infoEcommerceSync" in response.text
        assert "infoWhatsapp" in response.text

    def test_settings_shows_whatsapp_pilot_hint(self, client):
        response = client.get("/settings")
        assert response.status_code == 200
        assert "pilotHintWhatsappSettings" in response.text
        assert "Notificaciones WhatsApp habilitadas" in response.text

    def test_settings_has_ecommerce_sync_controls(self, client):
        response = client.get("/settings")
        assert response.status_code == 200
        assert "ecommerceSyncCard" in response.text
        assert "btnSaveEcommerce" in response.text

    def test_settings_has_whatsapp_meta_section(self, client):
        response = client.get("/settings")
        assert response.status_code == 200
        html = response.text
        assert "waSettingsCard" in html
        assert "btnSaveWa" in html
        assert "waPhoneId" in html
        assert "waToken" in html
        assert "waLang" in html
        assert "waTokenStatus" in html


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


class TestOnboardingPage:
    def test_onboarding_renders(self, client):
        response = client.get("/onboarding")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_onboarding_has_connect_cta(self, client):
        response = client.get("/onboarding")
        assert "btnConnect" in response.text
        assert "Tiendanube" in response.text

    def test_onboarding_has_step_by_step_and_copy_urls(self, client):
        response = client.get("/onboarding")
        html = response.text
        assert "steps-row" in html
        assert "txtOAuthCallback" in html
        assert "txtWebhookUrl" in html
        assert "/ayuda/conectar-tiendanube" in html

    def test_onboarding_shows_whatsapp_activation_hint(self, client):
        response = client.get("/onboarding")
        assert response.status_code == 200
        assert "pilotHintWhatsappOnboarding" in response.text
        assert "/settings" in response.text


class TestHelpTiendanubePage:
    def test_help_page_renders_public(self, client):
        response = client.get("/ayuda/conectar-tiendanube")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_help_page_has_steps_and_login_link(self, client):
        response = client.get("/ayuda/conectar-tiendanube")
        assert "Conectar tu tienda Tiendanube" in response.text
        assert "/login" in response.text
        assert "/register" in response.text


class TestStaticAssets:
    def test_css_loads(self, client):
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]
