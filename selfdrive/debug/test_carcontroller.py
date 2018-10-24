#!/usr/bin/env python
import time
import numpy as np
import zmq
from evdev import InputDevice
from select import select

from cereal import car
from common.realtime import Ratekeeper
from common.params import Params

import selfdrive.messaging as messaging
from selfdrive.services import service_list
from selfdrive.car.car_helpers import get_car


if __name__ == "__main__":
  # ***** connect to joystick *****
  # we use a Mad Catz V.1
  dev = InputDevice("/dev/input/event8")
  # print dev

  button_values = [0]*7
  axis_values = [0.0, 0.0, 0.0]

  # ***** connect to car *****
  context = zmq.Context()
  logcan = messaging.sub_sock(context, service_list['can'].port)
  sendcan = messaging.pub_sock(context, service_list['sendcan'].port)

  CI, CP = get_car(logcan, sendcan)
  CC = car.CarControl.new_message()

  params = Params()
  params.put("CarParams", CP.to_bytes())

  rk = Ratekeeper(100)

  # Toggle "enabled" by button 0
  enabled = False
  enable_button_prev = False

  while 1:
    # **** handle joystick ****
    r, w, x = select([dev], [], [], 0.0)
    if dev in r:
      for event in dev.read():
        # button event
        if event.type == 1:
          btn = event.code - 288
          if btn >= 0 and btn < 7:
            button_values[btn] = int(event.value)

        # axis move event
        if event.type == 3:
          if event.code < 3:
            if event.code == 2:
              axis_values[event.code] = np.clip((255-int(event.value))/250.0, 0.0, 1.0)
            else:
              DEADZONE = 5
              if event.value-DEADZONE < 128 and event.value+DEADZONE > 128:
                event.value = 128
              axis_values[event.code] = np.clip((int(event.value)-128)/120.0, -1.0, 1.0)

    # print axis_values, button_values
    # **** handle car ****

    CS = CI.update(CC)
    #print CS
    CC = car.CarControl.new_message()


    enable_button = bool(button_values[0])
    if enable_button and not enable_button_prev:
      enabled = not enabled
    CC.enabled = enabled
    enable_button_prev = enable_button

    CC.actuators.gas = float(np.clip(-axis_values[1], 0, 1.0))
    CC.actuators.brake = float(np.clip(axis_values[1], 0, 1.0))
    CC.actuators.steer = float(-axis_values[0])

    CC.hudControl.speedVisible = bool(button_values[1])
    CC.hudControl.lanesVisible = bool(button_values[2])
    CC.hudControl.leadVisible = bool(button_values[3])

    CC.cruiseControl.override = False
    CC.cruiseControl.cancel = bool(button_values[-1])

    CC.hudControl.setSpeed = float(axis_values[2] * 100.0)

    # TODO: test alerts
    CC.hudControl.visualAlert = "none"
    CC.hudControl.audibleAlert = "none"

    #print CC

    CI.apply(CC)

    rk.keep_time()



