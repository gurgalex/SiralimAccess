"""Hang monitor
Adapted from
https://github.com/servo/servo/blob/master/components/background_hang_monitor/background_hang_monitor.rs
https://medium.com/programming-servo/programming-servo-a-background-hang-monitor-73e89185ce1
https://medium.com/@polyglot_factotum/rust-concurrency-patterns-communicate-by-sharing-your-sender-re-visited-9d42e6dfecfa"""

import multiprocessing
import queue
import threading
import time
from typing import NewType, Protocol, Union, Any, Optional
from dataclasses import dataclass

from subot.utils import assert_never


@dataclass
class HangAnnotation:
    data: dict


ComponentId = NewType('ComponentId', str)


@dataclass
class Long:
    component_id: ComponentId
    annotation: HangAnnotation


HangAlert = Union[Long]


@dataclass
class Hang:
    alert: HangAlert


HangMonitorAlert = Union[Hang]


@dataclass
class Register:
    component_id: ComponentId
    hang_timeout_seconds: float


@dataclass
class Unregister:
    pass


@dataclass
class NotifyWait:
    pass


@dataclass
class NotifyActivity:
    annotation: HangAnnotation


MonitoredComponentMsg = Union[Register, Unregister, NotifyActivity, NotifyWait]


@dataclass
class MonitoredComponent:
    last_activity: float
    last_annotation: Optional[HangAnnotation]
    hang_timeout_seconds: float
    sent_hang_alert: bool = False
    # wait until first activity is posted to set to false
    is_waiting: bool = True


class HangMonitorChan:
    def __init__(self, sender: queue.Queue, component_id: ComponentId):
        self.sender = sender
        self.component_id = component_id
        self.disconnected = False

    def send(self, msg: MonitoredComponentMsg):
        if self.disconnected:
            return

        self.sender.put((self.component_id, msg))

    def notify_activity(self, annotation: HangAnnotation):
        msg = NotifyActivity(annotation)
        self.send(msg)

    def notify_wait(self):
        msg = NotifyWait()
        self.send(msg)

    def unregister(self):
        msg = Unregister()
        self.send(msg)


class HangRegister:
    def __init__(self, sender: queue.Queue):
        self.sender = sender


class HangMonitorWorker(threading.Thread):
    """Moniter threads to make sure they didn't crash.
    Notify that a thread crashed by `interested`"""

    def __init__(self, hang_notify_queue: 'multiprocessing.Queue[HangMonitorAlert]', control_port: queue.Queue
                 , **kwargs):
        super().__init__(**kwargs)
        self.interested = hang_notify_queue
        self.monitered_components: dict[ComponentId, MonitoredComponent] = dict()
        self.control_port = control_port

        self.monitee_recv_queue = queue.Queue()
        self.should_exit = False

    def handle_control_msg(self, msg: Any):
        print(f"got control msg = {msg=}")

    def handle_monitee_msg(self, msg: MonitoredComponentMsg):
        component_id, data = msg
        if isinstance(data, Register):
            component = MonitoredComponent(last_activity=time.time(),
                                           last_annotation=None,
                                           hang_timeout_seconds=data.hang_timeout_seconds,
                                           is_waiting=True,
                                           sent_hang_alert=False,
                                           )
            self.monitered_components[component_id] = component
        elif isinstance(data, Unregister):
            try:
                self.monitered_components.pop(component_id)
            except KeyError:
                raise Exception(f"Received Unregister for an unknown component {component_id=}")

        elif isinstance(data, NotifyActivity):
            try:
                component = self.monitered_components[component_id]
            except KeyError:
                raise Exception(f"Received NotifyWait for an unknown component {component_id=}")

            component.last_activity = time.time()
            component.last_annotation = data.annotation
            component.sent_hang_alert = False
            component.is_waiting = False

        elif isinstance(data, NotifyWait):
            component = self.monitered_components.get(component_id)
            if not component:
                raise Exception(f"monitored component {component_id} is not registered")
            component.last_activity = time.time()
            component.sent_hang_alert = False
            component.is_waiting = True
        else:
            assert_never(data)

    def run(self):
        while not self.should_exit:
            try:
                if msg := self.monitee_recv_queue.get(timeout=0.25):
                    self.handle_monitee_msg(msg)
            except queue.Empty:
                pass

            has_another_msg = True
            while has_another_msg:
                # handle any new messages came before sleeping
                try:
                    another_msg = self.monitee_recv_queue.get_nowait()
                    self.handle_monitee_msg(another_msg)
                except queue.Empty:
                    has_another_msg = False

            try:
                control_msg = self.control_port.get_nowait()
                self.handle_control_msg(control_msg)
            except queue.Empty:
                pass

            self.perform_hang_check()

    def perform_hang_check(self):
        for component_id, monitered in self.monitered_components.items():
            if monitered.is_waiting:
                continue

            last_annotation = monitered.last_annotation
            elapsed = time.time() - monitered.last_activity
            if elapsed > monitered.hang_timeout_seconds:
                if monitered.sent_hang_alert:
                    continue

                self.interested.put(
                    Hang(alert=Long(component_id, annotation=last_annotation))
                )
                monitered.sent_hang_alert = True
                continue

    def register_component(self, thread_handle: threading.Thread, hang_timeout_seconds: float) -> HangMonitorChan:
        component_id = ComponentId(thread_handle.name)

        bhm_chan = HangMonitorChan(component_id=component_id, sender=self.monitee_recv_queue)
        bhm_chan.send(Register(component_id=component_id, hang_timeout_seconds=hang_timeout_seconds))

        return bhm_chan
