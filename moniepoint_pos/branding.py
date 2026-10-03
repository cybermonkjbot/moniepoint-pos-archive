"""Client branding for the existing app-loading screen."""
from moniepoint_pos.shop_ui import enabled


def website_context(context):
    if enabled():
        context.splash_image = "/assets/moniepoint_pos/images/k3ls-loading-logo.png"
