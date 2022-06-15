from core.base.model.AliceSkill import AliceSkill
from core.base.model.ProjectAliceObject import ProjectAliceObject
from core.base.model.Intent import Intent
from core.device.model.Device import Device
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import Online, IntentHandler
import os
from glob import glob
from typing import List


class TVControl(AliceSkill):
	"""
	Author: philipp2310
	Description: Control your TV with alice
		You need fixed IPs for your devices to make this work reliable.
		Otherwise you would have to rediscover the devices after every Alice restart
	"""

	def __init__(self):
		super().__init__()


	@IntentHandler('TVC_addDevice')
	def searchDeviceIntent(self, session: DialogSession):
		#TVController.discoverAll()
		pass


	@IntentHandler('TVC_turnOn')
	def turnOnIntent(self, session: DialogSession):
		try:
			self.getDevice(session=session).turnOn()
		except NameError:
			self.unsupportedFeature(session=session)


	@IntentHandler('TVC_turnOff')
	def turnOffIntent(self, session: DialogSession):
		try:
			self.getDevice(session=session).turnOff()
		except NameError:
			self.unsupportedFeature(session=session)


	@IntentHandler('TVC_mute')
	def mute(self, session: DialogSession):
		try:
			self.getDevice(session=session).mute()
		except NameError:
			self.unsupportedFeature(session=session)


	@IntentHandler('TVC_unmute')
	def unmute(self, session: DialogSession):
		try:
			self.getDevice(session=session).unmute()
		except NameError:
			self.unsupportedFeature(session=session)


	@IntentHandler('TVC_channel')
	def channel(self, session: DialogSession):
		try:
			self.getDevice(session=session).setChannel(1)
		except NameError:
			self.unsupportedFeature(session=session)
		#todo prepare input, distinguish:
		# one up
		# one down
		# to 1-99
		# back
		pass


	def getDevice(self, session):
		return self.LocationManager.getLocationsForSession(session=session, noneIsEverywhere=False)


	def unsupportedFeature(self, session):
		# text out: This Feature is not supported
		self.MqttManager.endDialog(session.sessionId, self.randomTalk('TVC_notSupported', []), session.siteId)
