#!/usr/bin/env python3
"""Apply method renames across all affected files to resolve duplicate method names."""

import json
import re
import os

BASE = os.path.join(os.path.dirname(__file__), "..")

SRC_DIR = os.path.join(BASE, "eval_checker/multi_turn_eval/func_source_code")
DOC_DIR = os.path.join(BASE, "data/multi_turn_func_doc")
PATCH_DIR = os.path.join(BASE, "data/text/server_failure_patch")
FAILING_TOOLS = os.path.join(BASE, "data/text/failing_tools.json")

# ============================================================================
# RENAME MAPPINGS: server_file_stem -> {old_method: new_method}
# ============================================================================

RENAMES = {
    # --- Email: OutlookAPI (vs GmailAPI) ---
    "outlook": {
        "add_contact": "add_person",
        "create_draft": "compose_draft",
        "forward_email": "forward_mail_item",
        "get_email": "get_mail_item",
        "list_contacts": "list_people",
        "list_emails": "list_mail_items",
        "mark_as_read": "set_as_read",
        "mark_as_unread": "set_as_unread",
        "reply_to_email": "reply_to_conversation",
        "search_emails": "query_mail_items",
        "send_draft": "send_composed_draft",
        "send_email": "send_mail_item",
        "switch_user": "set_active_user",
        "update_draft": "update_composed_draft",
    },

    # --- Food Delivery: DoorDashAPI (vs UberEatsOrderAPI) ---
    "doordash": {
        "add_address": "add_delivery_location",
        "add_payment_method": "add_dash_payment",
        "cancel_order": "cancel_dash",
        "get_available_offers": "get_promos",
        "get_menu": "get_store_menu",
        "get_order": "get_dash",
        "get_order_history": "get_dash_history",
        "get_profile": "get_dasher_profile",
        "get_restaurant": "get_store_details",
        "list_payment_methods": "list_dash_payments",
        "place_order": "place_dash",
        "rate_order": "rate_dash",
        "remove_address": "remove_delivery_location",
        "search_restaurants": "search_stores",
        "set_default_address": "set_primary_delivery_location",
        "set_default_payment_method": "set_primary_dash_payment",
        "track_order": "track_dash",
        "update_profile": "update_dasher_profile",
    },

    # --- Ridesharing: LyftAPI (vs UberAPI) ---
    "lyft": {
        "add_saved_place": "save_location",
        "apply_offer": "redeem_promo",
        "cancel_ride": "cancel_trip",
        "get_driver_info": "get_driver_details",
        "get_ride": "get_trip",
        "get_user_profile": "get_rider_profile",
        "list_offers": "list_promos",
        "list_ride_types": "list_ride_modes",
        "list_rides": "list_trip_history",
        "rate_ride": "rate_trip",
        "remove_saved_place": "delete_location",
        "request_ride": "book_ride",
        "tip_driver": "add_gratuity",
    },

    # --- Payments: ZelleAPI (vs VenmoAPI) ---
    "zelle": {
        "activate_funding_source": "enroll_bank_account",
        "add_contact": "add_recipient",
        "add_funding_source": "link_bank_account",
        "cancel_request": "cancel_transfer_request",
        "cancel_transaction": "cancel_transfer",
        "deactivate_funding_source": "unenroll_bank_account",
        "get_contact": "get_recipient",
        "get_profile": "get_account_profile",
        "get_request": "get_transfer_request",
        "get_transaction": "get_transfer",
        "list_contacts": "list_recipients",
        "list_funding_sources": "list_enrolled_banks",
        "list_requests": "list_transfer_requests",
        "list_transactions": "list_transfers",
        "remove_contact": "remove_recipient",
        "request_money": "request_transfer",
        "respond_to_request": "respond_to_transfer_request",
        "send_money": "send_transfer",
    },

    # --- Travel: ExpediaAPI (vs BookingAPI) ---
    "expedia": {
        "cancel_booking": "cancel_itinerary",
        "create_booking": "create_itinerary",
        "get_booking": "get_itinerary",
        "get_property": "get_hotel_details",
        "get_room_types": "get_room_availability",
        "get_user_profile": "get_traveler_profile",
        "list_bookings": "list_trips",
        "modify_booking": "update_itinerary",
        "search_properties": "search_hotels",
    },

    # --- Wiki: ConfluenceAPI (vs NotionAPI) ---
    "confluence": {
        "create_page": "publish_content",
        "delete_page": "trash_content",
        "get_page": "fetch_content",
        "get_user_profile": "retrieve_profile",
        "list_pages": "list_space_content",
        "share_page": "grant_content_access",
        "update_page": "revise_content",
    },

    # --- Shopping: WalmartAPI (vs AmazonAPI, TargetAPI) ---
    "walmart": {
        "add_address": "add_shipping_address",
        "add_payment_method": "add_wallet_payment",
        "add_to_cart": "add_item_to_basket",
        "apply_promo_code": "redeem_promo_code",
        "cancel_order": "cancel_purchase",
        "get_cart": "get_basket",
        "get_order_details": "get_purchase_details",
        "get_product_details": "get_item_details",
        "get_reviews": "get_item_reviews",
        "list_addresses": "list_shipping_addresses",
        "list_payment_methods": "list_wallet_payments",
        "place_order": "submit_order",
        "remove_from_cart": "remove_item_from_basket",
        "search_products": "browse_products",
        "select_fulfillment": "choose_fulfillment",
        "start_return": "initiate_return",
        "update_cart_item": "update_basket_item",
        "write_review": "submit_review",
    },

    # --- Shopping: TargetAPI (vs AmazonAPI, WalmartAPI) ---
    "target": {
        "add_address": "save_address",
        "add_payment_method": "save_payment_method",
        "add_to_cart": "put_in_cart",
        "apply_promo_code": "apply_discount_code",
        "cancel_order": "void_order",
        "get_cart": "view_cart",
        "get_order_details": "get_order_info",
        "get_product_details": "get_merchandise_info",
        "get_reviews": "read_reviews",
        "list_addresses": "get_address_book",
        "list_payment_methods": "get_saved_payments",
        "place_order": "checkout_order",
        "remove_from_cart": "pull_from_cart",
        "search_products": "search_merchandise",
        "select_fulfillment": "set_fulfillment_method",
        "start_return": "begin_return",
        "update_cart_item": "modify_cart_item",
        "write_review": "post_review",
    },

    # --- Shopping: InstacartAPI (vs AmazonAPI, WalmartAPI, TargetAPI) ---
    "instacart": {
        "add_address": "add_drop_off_address",
        "add_payment_method": "add_payment_option",
        "add_to_cart": "add_grocery_item",
        "apply_coupon": "redeem_coupon",
        "cancel_order": "cancel_delivery",
        "get_cart": "get_grocery_cart",
        "get_delivery_windows": "get_delivery_slots",
        "get_product_details": "get_grocery_details",
        "list_addresses": "list_drop_off_addresses",
        "list_payment_methods": "list_payment_options",
        "remove_from_cart": "remove_grocery_item",
        "search_products": "search_grocery_items",
        "update_cart_item": "update_grocery_quantity",
    },

    # --- Music: SpotifyAPI (vs AppleMusicAPI) ---
    "spotify": {
        "add_tracks_to_playlist": "queue_tracks_to_playlist",
        "create_playlist": "create_new_playlist",
        "delete_playlist": "remove_playlist",
        "follow_artist": "subscribe_to_artist",
        "get_artist": "fetch_artist",
        "get_artist_top_tracks": "fetch_top_tracks",
        "get_followed_artists": "get_subscribed_artists",
        "get_playback_state": "get_now_playing",
        "get_playlist": "fetch_playlist",
        "get_user_profile": "get_listener_profile",
        "pause_playback": "pause_stream",
        "play_track": "start_track",
        "remove_tracks_from_playlist": "dequeue_tracks_from_playlist",
        "resume_playback": "resume_stream",
        "seek_track": "seek_position",
        "set_repeat": "toggle_repeat",
        "set_shuffle": "toggle_shuffle",
        "share_track": "share_track_link",
        "skip_to_next": "next_track",
        "skip_to_previous": "previous_track",
        "unfollow_artist": "unsubscribe_from_artist",
        "update_playlist_details": "modify_playlist_details",
    },

    # --- Finance: RobinhoodAPI (vs FidelityAPI) ---
    "robinhood": {
        "add_to_watchlist": "add_to_collection",
        "cancel_order": "cancel_trade",
        "deposit_funds": "instant_deposit",
        "get_order": "get_trade",
        "get_stock_quote": "get_asset_quote",
        "get_watchlist": "get_collection",
        "list_orders": "list_trades",
        "place_order": "place_trade",
        "remove_from_watchlist": "remove_from_collection",
        "search_stocks": "search_assets",
        "withdraw_funds": "withdraw_to_bank",
    },

    # === Cross-domain conflict fixes ===

    # VenmoAPI: conflicts with GmailAPI (add_contact, list_contacts),
    #           GoogleMapReviewAPI/UberEatsOrderAPI (get_profile)
    "venmo": {
        "add_contact": "add_friend",
        "list_contacts": "list_friends",
        "get_profile": "get_account_summary",
    },

    # GoogleMapReviewAPI: conflicts with UberEatsOrderAPI/VenmoAPI (get_profile),
    #                     UberAPI (remove_saved_place)
    "google_map_review": {
        "get_profile": "get_reviewer_profile",
        "remove_saved_place": "unpin_place",
    },

    # UberEatsOrderAPI: conflicts with AmazonAPI (add_address, add_payment_method,
    #                   cancel_order, list_payment_methods, place_order)
    #                   and VenmoAPI/GoogleMapReview (get_profile)
    "uber_eats": {
        "add_address": "register_delivery_address",
        "add_payment_method": "register_payment_method",
        "cancel_order": "cancel_food_order",
        "get_profile": "get_eater_profile",
        "list_payment_methods": "get_registered_payments",
        "place_order": "submit_food_order",
    },

    # YelpAPI: write_review conflicts with AmazonAPI
    "yelp": {
        "write_review": "compose_review",
    },

    # FidelityAPI: get_user_profile conflicts with BookingAPI, WeatherComAPI
    "fidelity": {
        "get_user_profile": "get_investor_profile",
    },

    # WeatherComAPI: get_user_profile conflicts with BookingAPI, FidelityAPI
    "weather_com": {
        "get_user_profile": "get_weather_preferences",
    },

    # GoogleCalendarAPI: get_user_profile conflicts with BookingAPI
    "google_calendar": {
        "get_user_profile": "get_calendar_settings",
    },
}

# Map file stems to API class names
STEM_TO_CLASS = {
    "outlook": "OutlookAPI",
    "doordash": "DoorDashAPI",
    "lyft": "LyftAPI",
    "zelle": "ZelleAPI",
    "expedia": "ExpediaAPI",
    "confluence": "ConfluenceAPI",
    "walmart": "WalmartAPI",
    "target": "TargetAPI",
    "instacart": "InstacartAPI",
    "spotify": "SpotifyAPI",
    "robinhood": "RobinhoodAPI",
    "venmo": "VenmoAPI",
    "google_map_review": "GoogleMapReviewAPI",
    "uber_eats": "UberEatsOrderAPI",
    "yelp": "YelpAPI",
    "fidelity": "FidelityAPI",
    "weather_com": "WeatherComAPI",
    "google_calendar": "GoogleCalendarAPI",
}


def rename_in_py(stem, renames):
    """Rename method definitions and internal calls in a .py source file."""
    path = os.path.join(SRC_DIR, f"{stem}.py")
    if not os.path.exists(path):
        print(f"  SKIP (no file): {path}")
        return

    with open(path, "r") as f:
        content = f.read()

    for old, new in renames.items():
        # Rename method definitions: def old_name(
        content = re.sub(
            rf'\bdef {re.escape(old)}\b',
            f'def {new}',
            content,
        )
        # Rename self.old_name( calls
        content = re.sub(
            rf'\bself\.{re.escape(old)}\b',
            f'self.{new}',
            content,
        )

    with open(path, "w") as f:
        f.write(content)
    print(f"  Updated: {path} ({len(renames)} methods)")


def rename_in_json(stem, renames):
    """Rename method names and descriptions in a JSONL function doc file."""
    path = os.path.join(DOC_DIR, f"{stem}.json")
    if not os.path.exists(path):
        print(f"  SKIP (no file): {path}")
        return

    lines = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                lines.append("")
                continue
            entry = json.loads(line)
            name = entry.get("name", "")
            if name in renames:
                entry["name"] = renames[name]
                # Update description: replace old method name references
                desc = entry.get("description", "")
                for old, new in renames.items():
                    desc = desc.replace(old, new)
                entry["description"] = desc
            lines.append(json.dumps(entry, ensure_ascii=False))

    with open(path, "w") as f:
        f.write("\n".join(lines))
        if lines and lines[-1] != "":
            f.write("\n")
    print(f"  Updated: {path}")


def rename_in_patches(stem, renames, class_name):
    """Rename method names in a server patch file."""
    # Try both naming conventions
    for pattern in [f"patches_{stem}.py", f"{stem}_patches.py"]:
        path = os.path.join(PATCH_DIR, pattern)
        if os.path.exists(path):
            break
    else:
        return  # No patch file

    with open(path, "r") as f:
        content = f.read()

    changed = False
    for old, new in renames.items():
        # Rename in _register_patch("method_name", ...)
        old_pattern = f'_register_patch("{old}"'
        new_pattern = f'_register_patch("{new}"'
        if old_pattern in content:
            content = content.replace(old_pattern, new_pattern)
            changed = True

        # Rename function definition names (e.g., def s3_get_astronomy -> ...)
        # These contain the old method name in the function name
        content = re.sub(
            rf'\bdef (\w*){re.escape(old)}\b',
            lambda m: f'def {m.group(1)}{new}',
            content,
        )

    if changed:
        with open(path, "w") as f:
            f.write(content)
        print(f"  Updated: {path}")


def rename_in_failing_tools():
    """Rename all server method references in failing_tools.json."""
    entries = []
    with open(FAILING_TOOLS, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    # Build a mapping of ClassAPI.old_method -> ClassAPI.new_method
    class_method_renames = {}
    for stem, renames in RENAMES.items():
        class_name = STEM_TO_CLASS[stem]
        for old, new in renames.items():
            class_method_renames[f"{class_name}.{old}"] = f"{class_name}.{new}"

    # Also build text-field rename patterns: "ServiceName old_method" -> "ServiceName new_method"
    # Map class names to their human-readable service names used in text
    class_to_service_names = {
        "OutlookAPI": ["Outlook"],
        "DoorDashAPI": ["DoorDash"],
        "LyftAPI": ["Lyft"],
        "ZelleAPI": ["Zelle"],
        "ExpediaAPI": ["Expedia"],
        "ConfluenceAPI": ["Confluence"],
        "WalmartAPI": ["Walmart"],
        "TargetAPI": ["Target"],
        "InstacartAPI": ["Instacart"],
        "SpotifyAPI": ["Spotify"],
        "RobinhoodAPI": ["Robinhood"],
        "VenmoAPI": ["Venmo"],
        "GoogleMapReviewAPI": ["Google Map", "Google Maps"],
        "UberEatsOrderAPI": ["Uber Eats", "UberEats"],
        "YelpAPI": ["Yelp"],
        "FidelityAPI": ["Fidelity"],
        "WeatherComAPI": ["Weather.com"],
        "GoogleCalendarAPI": ["Google Calendar"],
    }

    total_changes = 0
    for i, entry in enumerate(entries):
        entry_str = json.dumps(entry, ensure_ascii=False)
        original = entry_str

        # Replace ClassAPI.method patterns (in structured fields like failure_injection, ground_truth, etc.)
        for old_ref, new_ref in class_method_renames.items():
            entry_str = entry_str.replace(old_ref, new_ref)

        # Replace method names in text fields where they appear near service name context
        for stem, renames in RENAMES.items():
            class_name = STEM_TO_CLASS[stem]
            service_names = class_to_service_names.get(class_name, [])
            for svc in service_names:
                for old, new in renames.items():
                    # "ServiceName method_name" or "ServiceName: method_name"
                    entry_str = entry_str.replace(f"{svc} {old}", f"{svc} {new}")
                    entry_str = entry_str.replace(f"{svc}: {old}", f"{svc}: {new}")
                    entry_str = entry_str.replace(f"{svc}'s {old}", f"{svc}'s {new}")

        if entry_str != original:
            entries[i] = json.loads(entry_str)
            total_changes += 1

    with open(FAILING_TOOLS, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"  Updated failing_tools.json: {total_changes} entries modified")


def main():
    for stem, renames in RENAMES.items():
        class_name = STEM_TO_CLASS[stem]
        print(f"\n=== {class_name} ({stem}) — {len(renames)} methods ===")
        rename_in_py(stem, renames)
        rename_in_json(stem, renames)
        rename_in_patches(stem, renames, class_name)

    print("\n=== Updating failing_tools.json ===")
    rename_in_failing_tools()

    print("\nDone!")


if __name__ == "__main__":
    main()
