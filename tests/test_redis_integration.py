import asyncio
import multiprocessing
import os
from unittest import skipUnless
from uuid import uuid4

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.test import SimpleTestCase


def receive_in_child(group, ready, received):
    async def run():
        layer = get_channel_layer()
        channel = await layer.new_channel()
        await layer.group_add(group, channel)
        ready.put(os.getpid())
        event = await asyncio.wait_for(layer.receive(channel), timeout=10)
        received.put(event)
        await layer.group_discard(group, channel)
        await layer.close_pools()

    asyncio.run(run())


@skipUnless(
    os.environ.get('NEXTROUTER_REDIS_TEST') == '1'
    and settings.CHANNEL_LAYERS.get('default', {}).get('BACKEND') == 'channels_redis.core.RedisChannelLayer',
    'Exige opt-in e Redis descartável em settings específicos; a suíte local usa memória.',
)
class RedisMultiprocessTests(SimpleTestCase):
    def test_broadcast_crosses_process_boundary(self):
        context = multiprocessing.get_context('spawn')
        ready, received = context.Queue(), context.Queue()
        group = f'test_travel_{uuid4().hex}'
        child = context.Process(target=receive_in_child, args=(group, ready, received))
        child.start()
        try:
            self.assertNotEqual(ready.get(timeout=15), os.getpid())
            event = {'type': 'location.update'}
            async_to_sync(get_channel_layer().group_send)(group, event)
            self.assertEqual(received.get(timeout=15), event)
        finally:
            child.join(timeout=3)
            if child.is_alive():
                child.terminate()
                child.join(timeout=3)
            ready.close()
            received.close()
        self.assertEqual(child.exitcode, 0)
