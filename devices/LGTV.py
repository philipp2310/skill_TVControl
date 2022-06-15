import sqlite3
from core.device.model.Device import Device
from core.device.model.DeviceAbility import DeviceAbility
from core.dialog.model.DialogSession import DialogSession
from pywebostv.discovery import *    # Because I'm lazy, don't do this.
from pywebostv.connection import *
from pywebostv.connection import WebOSClient
from pywebostv.controls import *
from pathlib import Path
from wakeonlan import send_magic_packet
import json
from datetime import datetime

from core.webui.model.DeviceClickReactionAction import DeviceClickReactionAction
from core.webui.model.OnDeviceClickReaction import OnDeviceClickReaction

from typing import Optional, Dict, Union


class LGTV(Device):

	def __init__(self, data: Union[sqlite3.Row, Dict]):
		super().__init__(data)
		ip = self.getConfig('ip') or None
		store = json.loads(self.getParam('store'))

		if ip and store and 'client_key' in store:
			self.client = WebOSClient(ip)
			try:
				self.client.connect()
				for prompt in self.client.register(store):
					pass
			except OSError:
				pass  # not connected is "ok"
		else:
			self.client = None

	@classmethod
	def getDeviceTypeDefinition(cls) -> dict:
		return {
			'deviceTypeName'        : 'LGTV',
			'perLocationLimit'      : 0,
			'totalDeviceLimit'      : 0,
			'allowLocationLinks'    : True,
			'allowHeartbeatOverride': True,
			'heartbeatRate'         : 60,
			'deviceSettings'        : dict(),
			'abilities'             : [DeviceAbility.ALERT, DeviceAbility.NOTIFY]
		}


	def getDeviceIcon(self, path: Optional[Path] = None) -> Path:
		"""
		Return the path of the icon representing the current status of the device
		e.g. a light bulb can be on or off and display its status
		:return: the icon file path
		"""
		base = self._typeName
		status = self.getStatus()
		icon = Path(f'{self.Commons.rootDir()}/skills/{self.skillName}/devices/img/{base}'
		            f'{f"_{status}" if status else ""}.png')
		return super().getDeviceIcon(icon)


	def prepareClient(self) -> bool:
		if self.client is None:
			return False

		if self.client.stream is None or self.client.server_terminated:
			try:
				self.client.connect()
				for prompt in self.client.register(store):
					pass
			except OSError:
				pass  # not connected is "ok"


	def getStatus(self, connect:bool = True) -> str:
		"""
		Return a string containing the status of the device
		:return:
		"""
		if not self.client:
			return ''
		try:
			app = ApplicationControl(self.client)
			apps = app.list_apps()
			app_id = app.get_current()
			foreground_app = [x for x in apps if app_id == x["id"]][0]
			icon_url = foreground_app["icon"]
			self.logInfo(icon_url)
		except Exception as e:
			if connect:
				self.prepareClient()
				self.getStatus(connect=False)
			self.logInfo(e)
			return 'OFF'
		if self.client.server_terminated or self.client.client_terminated or not self.client.sock or not self.client.stream:
			return 'OFF'
		else:
			return 'ON'

	def onUIClick(self) -> dict:
		"""
		Called whenever a device's icon is clicked on the UI
		:return:
		"""

		if not self.uid:
			self.discover()
			return OnDeviceClickReaction(
				action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
				data='notifications.info.pleasePlugDevice'
			).toDict()

		self.prepareClient()
		status = self.getStatus()
		if status == 'OFF':
			if self.turnOn():
				return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
				                             data={"body": f'Device turned on.'}).toDict()
			else:
				return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
				                             data={"body": f'Couldn\'t turn on Device.'}).toDict()

		else:
			try:
				tv_control = TvControl(self.client)
				prog = tv_control.get_current_program()
				channel = prog['channel']['channelName']
				# '2022,06,14,02,39,28'
				currentTime = datetime.now().strftime("%Y,%m,%d,%H,%M,%S")
				runningShows = [show for show in prog['programList'] if show['localStartTime'] < currentTime and show['localEndTime'] > currentTime ]

				startTime = datetime.strptime(runningShows[0]["localStartTime"], "%Y,%m,%d,%H,%M,%S")
				endTime = datetime.strptime(runningShows[0]["localEndTime"], "%Y,%m,%d,%H,%M,%S")

				return OnDeviceClickReaction(action=DeviceClickReactionAction.INFO_NOTIFICATION.value,
				                             data={ "body": f'{channel}: <br/> {startTime.strftime("%H:%M")} - {endTime.strftime("%H:%M")} <br/> {runningShows[0]["programName"]}' } ).toDict()
			except IOError as e:
				self.logInfo(e)
			return OnDeviceClickReaction(action=DeviceClickReactionAction.NONE.value).toDict()


	def discover(self, replyOnSiteId: str = '', session: DialogSession = None) -> bool:
		ip = self.getConfig('ip') or None
		self.logInfo(f'Setting up device for ip <{ip}>')

		store = json.loads(self.getParam('store'))
		if store and 'client_key' in store:
			# try connect and throw away data on fail
			client = WebOSClient(ip)
			client.connect()
			for prompt in client.register(store):
				if prompt == WebOSClient.REGISTERED:
					self.pairingDone(uid=ip)
					return True
				else:
					store = dict()
					break
		else:
			store = dict()

		# discover all devices on the network
		allClients = WebOSClient.discover()

		# remove known devices
		# get DB devices
		existingDevices = self.DeviceManager.getDevicesByType(deviceType=self._typeName)
		self.logInfo(f'found a total of <{len(existingDevices)}> devices')

		newClients = [c for c in allClients if
		              dict(c.handshake_headers)['Host'].split(":", 2)[0] not in [k.getConfig('ip') for k in
		                                                                         existingDevices]]

		self.logInfo(f'found a total of <{len(newClients)}> devices after filter')

		for client in newClients:
			client.connect()
			self.logInfo(f'connecting')
			for status in client.register(store):
				if status == WebOSClient.PROMPTED:
					# voice out: Please confirm on device X
					self.logInfo("Please accept the connection on the TV!")
					#yield PairAction(actionType=PairActionType.ACTION_REQUIRED)
				elif status == WebOSClient.REGISTERED:
					# store data
					self._pairDevice(webosclient=client, store=store)
					# voice out: I successfully connected to a new TV
					self.logInfo("Registration successful!")
					#return PairAction(actionType=PairActionType.PAIRING_DONE, device=device)


	def _pairDevice(self, webosclient: WebOSClient, store: Dict) -> bool:
		ip: str = dict(webosclient.handshake_headers)['Host'].split(":", 2)[0]
		mac: str = webosclient.info().get('device_id', '')
		self.updateConfig('mac', mac)
		self.updateConfig('ip', ip)
		self.updateParam('store', json.dumps(store))
		self.pairingDone(uid=ip)
		self.client = webosclient
		return True


	def mute(self):
		media = MediaControl(self.client)
		media.mute(True)


	def unmute(self):
		media = MediaControl(self.client)
		media.mute(False)


	def turnOff(self) -> bool:
		system = SystemControl(self.client)
		system.power_off()
		return True


	def turnOn(self) -> bool:
		if self.getConfig('mac'):
			send_magic_packet(self.getConfig('mac'))
			self.prepareClient()
			return True
		return False
