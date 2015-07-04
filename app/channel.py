import asyncio
import collections


class ChannelEmpty(Exception):
    pass


class ChannelClosed(Exception):
    pass


class Channel:
    _close_sentinel = object()

    def __init__(self, loop=None):
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._item_queue = collections.deque()
        self._get_queue = collections.deque()
        self._closed = False

    def _consume_done(self):
        # Futures are done if they have been cancelled while yielding
        # in get().
        while self._get_queue and self._get_queue[0].done():
            self._get_queue.popleft()

    def closed(self):
        """Returns True if the channel has been closed.

        Note: There may still be items left inside the channel!
        Use done() to check whether no more messages can be received.
        """
        return self._closed

    def close(self):
        """Closes the channel. Does nothing if the channel has already been closed

        A closed channel can no longer be used to *put* items.
        However, previously inserted items may still be read by calling get().
        """
        if not self.closed():
            # Put will not work anymore.
            # There may be leftover items in the queue.
            self._closed = True
            while self._get_queue and self._item_queue:
                getter = self._get_queue.popleft()
                if getter.done():
                    continue  # cancelled, pick next one

                value = self._item_queue.popleft()
                getter.set_result(value)

            # Getters without a matching item in the queue
            # will never receive one. Unblock them with the sentinel value.
            while self._get_queue:
                getter = self._get_queue.popleft()
                if not getter.done():
                    getter.set_result(Channel._close_sentinel)

        assert not self._get_queue, "There mustn't be any more getters"

    def empty(self):
        """Returns true if the number of pending items is zero."""
        return self.pending() == 0

    def done(self):
        """Returns true if all pending messages have been consumed
           and no more messages can arrive.

           Equivalent to the condition `closed() and empty()`.
        """
        return self.empty() and self.closed()

    def pending(self):
        """Returns the number of currently available items.

        These items can be read using get_nowait without raising an error.
        """
        return len(self._item_queue)

    def put(self, item):
        """Puts a single item into the channel.

        Raises ChannelClosed if the channel has been closed.
        """
        if not self.try_put(item):
            raise ChannelClosed

    def try_put(self, item):
        """Tries to put a single item into the channel.

        Returns false if the channel is closed, True otherwise.
        """
        if self.closed():
            return False

        self._consume_done()
        if self._get_queue:
            assert not self._item_queue, "All items must have been popped"

            getter = self._get_queue.popleft()
            getter.set_result(item)
        else:
            self._item_queue.append(item)
        return True

    @asyncio.coroutine
    def get(self):
        """Reads the next item from the channel.

        Waits until an item is ready.
        Raises ChannelClosed if the channel has been closed and no item
        was left inside the internal queue.
        """

        if self._item_queue:
            assert not self._get_queue, "There mustn't be any getters"
            return self._item_queue.popleft()
        else:
            if self.closed():
                raise ChannelClosed

            getter = asyncio.Future(loop=self._loop)
            self._get_queue.append(getter)

            # getter will be cancelled when coroutine gets cancelled.
            item = (yield from getter)
            if item is Channel._close_sentinel:
                raise ChannelClosed
            return item

    def get_nowait(self):
        """Tries to read the next item from the channel.

        Raises ChannelClosed if the channel has been closed
        or ChannelEmpty if no item was available. Does not wait."""

        if self._item_queue:
            return self._item_queue.popleft()
        elif self.closed():
            raise ChannelClosed
        else:
            raise ChannelEmpty
