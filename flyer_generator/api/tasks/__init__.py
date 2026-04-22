"""arq task registry. Consumed by ``WorkerSettings.functions``.

Importing this module triggers the import of every task module, which is
how arq learns about them (it binds the task-name strings routes enqueue
with to the matching coroutine).
"""

from __future__ import annotations

from flyer_generator.api.tasks.brand_kit import task_fetch_brand_kit
from flyer_generator.api.tasks.brochure import task_generate_brochure
from flyer_generator.api.tasks.campaign import task_generate_campaign
from flyer_generator.api.tasks.flyer import task_generate_flyer
from flyer_generator.api.tasks.post import task_generate_post

ALL_TASKS = [
    task_fetch_brand_kit,
    task_generate_flyer,
    task_generate_brochure,
    task_generate_post,
    task_generate_campaign,
]

__all__ = [
    "ALL_TASKS",
    "task_fetch_brand_kit",
    "task_generate_flyer",
    "task_generate_brochure",
    "task_generate_post",
    "task_generate_campaign",
]
