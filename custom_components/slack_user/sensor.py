"""Slack User Sensor."""

import datetime
import logging
import voluptuous as vol
from homeassistant.const import CONF_ID, CONF_TOKEN, CONF_NAME
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from slack import WebClient
from slack.errors import SlackApiError

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_ATTR_ENTITY_ID = "entity_id"

SERVICE_SET_STATUS = "set_status"
SERVICE_ATTR_STATUS_TEXT = "status_text"
SERVICE_ATTR_STATUS_EMOJI = "status_emoji"
SERVICE_ATTR_EXPIRATION = "expiration"
SERVICE_SET_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(SERVICE_ATTR_STATUS_TEXT): cv.string,
        vol.Optional(SERVICE_ATTR_STATUS_EMOJI): cv.string,
        vol.Optional(SERVICE_ATTR_EXPIRATION): vol.Or("", cv.datetime)
    }
)

SERVICE_CLEAR_STATUS = "clear_status"
SERVICE_CLEAR_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_ATTR_ENTITY_ID): cv.entity_ids,
    }
)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Slack User Sensor based on config_entry."""

    user_id = entry.data.get(CONF_ID)
    token = entry.data.get(CONF_TOKEN)
    name = entry.data.get(CONF_NAME)

    client = WebClient(
        token=token, run_async=True, session=async_get_clientsession(hass)
    )

    try:
        await client.auth_test()
    except SlackApiError:
        _LOGGER.error("Error setting up Slack User Entry %s", name)
        return False

    slack_user = SlackUser(client, user_id, token, name)
    async_add_entities([slack_user], True)

    # Setup services
    platform = entity_platform.async_get_current_platform()

    async def async_service_handler(service_call):
        """Handle dispatched services."""
        assert platform is not None
        entities = await platform.async_extract_from_service(service_call)

        if not entities:
            return

        if service_call.service == SERVICE_SET_STATUS:
            status_text = service_call.data.get(SERVICE_ATTR_STATUS_TEXT)
            status_emoji = service_call.data.get(SERVICE_ATTR_STATUS_EMOJI)
            expiration = service_call.data.get(SERVICE_ATTR_EXPIRATION)
            [await entity.async_set_status(status_text, status_emoji, expiration) for entity in entities]

        elif service_call.service == SERVICE_CLEAR_STATUS:
            [await entity.async_clear_status() for entity in entities]

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_STATUS,
        async_service_handler,
        SERVICE_SET_STATUS_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_STATUS,
        async_service_handler,
        SERVICE_CLEAR_STATUS_SCHEMA,
    )


class SlackUser(Entity):
    """ Slack User."""

    def __init__(self, client, user_id, token, name):
        """Initialize the sensor."""

        self._client = client
        self._user_id = user_id
        self._name = name
        self._token = token

        self._available = False

        # profile info
        self._title = None
        self._real_name = None
        self._display_name = None
        self._status_text = None
        self._status_emoji = None
        self._entity_picture = None

    async def async_update(self):
        """Retrieve latest state."""

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._user_id

    @property
    def available(self):
        """Return True when state is known."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return True

    @property
    def entity_picture(self):
        """Return Entity Picture."""
        return None

    @property
    def state_attributes(self):
        """Return entity attributes."""

        attrs = {
        }

        return {k: v for k, v in attrs.items() if v is not None}

    async def async_set_status(self, status_text = None, status_emoji = None, expiration = None):
        new_text = self._status_text if status_text == None else status_text
        new_emoji = self._status_emoji if status_emoji == None else status_emoji

        if expiration == "" or expiration == None:
            expiration_ts = expiration
        else:
            expiration_ts = int(datetime.datetime.timestamp(expiration))

        self._client.api_call(
            api_method = "users.profile.set",
            json = {
                "profile": {
                    "status_text": new_text,
                    "status_emoji": new_emoji,
                    "status_expiration": expiration_ts
                }
            }
        )

        await self.async_update()

    async def async_clear_status(self):
       await self.async_set_status("", "", "")
