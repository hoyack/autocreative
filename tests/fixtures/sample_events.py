"""Sample EventInput instances for test fixtures."""

from flyer_generator.models import EventInput

SAMPLE_EVENT = EventInput(
    title="Neighborhood Clean-Up Day",
    date="Saturday, May 2, 2026",
    time="9:00 AM - 12:00 PM",
    location_name="Riverside Park Pavilion",
    location_address="123 Park Rd, San Antonio, TX 78205",
    fees="FREE",
    org="Friends of Riverside Park",
    style_concept="community outdoor event, park setting, sunny morning",
    style_preset="photorealistic",
    color_accent="#F59E0B",
)

SAMPLE_EVENT_WITH_URL = EventInput(
    title="Summer Music Festival",
    date="Saturday, June 15, 2026",
    time="4:00 PM - 10:00 PM",
    location_name="Downtown Amphitheater",
    location_address="456 Main St, Austin, TX 78701",
    fees="$25",
    org="Austin Music Foundation",
    url="https://austinmusic.org/summer2026",
    style_concept="outdoor music festival, stage lights, summer evening",
    style_preset="scifi",
    color_accent="#8B5CF6",
)
