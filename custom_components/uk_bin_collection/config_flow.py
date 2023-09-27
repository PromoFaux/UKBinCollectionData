import json

import aiohttp
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import callback
from homeassistant import config_entries

import logging

_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN, LOG_PREFIX


class UkBinCollectionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    def __init__(self):
        self.councils_data = None

    async def get_councils_json(self) -> object:
        """Returns an object of supported council's and their required fields."""
        # Fetch the JSON data from the provided URL
        url = "https://raw.githubusercontent.com/robbrad/UKBinCollectionData/0.12.0/uk_bin_collection/tests/input.json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data_text = await response.text()
                return json.loads(data_text)

    async def get_council_schema(self, council=str) -> vol.Schema:
        """Returns a config flow form schema based on a specific council's fields."""
        if self.councils_data is None:
            self.councils_data = await self.get_councils_json()
        council_schema = vol.Schema({})
        if "SKIP_GET_URL" not in self.councils_data[council]:
            council_schema = council_schema.extend(
                {vol.Required("url", default=""): cv.string}
            )
        if "uprn" in self.councils_data[council]:
            council_schema = council_schema.extend(
                {vol.Required("uprn", default=""): cv.string}
            )
        if "postcode" in self.councils_data[council]:
            council_schema = council_schema.extend(
                {vol.Required("postcode", default=""): cv.string}
            )
        if "house_number" in self.councils_data[council]:
            council_schema = council_schema.extend(
                {vol.Required("number", default=""): cv.string}
            )
        if "usrn" in self.councils_data[council]:
            council_schema = council_schema.extend(
                {vol.Required("usrn", default=""): cv.string}
            )
        return council_schema

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        # Extract council names and create a list of options for the dropdown
        self.councils_data = await self.get_councils_json()
        self.council_names = list(self.councils_data.keys())
        self.council_options = [
            self.councils_data[name]["wiki_name"] for name in self.council_names
        ]

        if user_input is not None:
            # Perform validation and setup here based on user_input
            if user_input["name"] is None or user_input["name"] == "":
                errors["base"] = "name"
            if user_input["council"] is None or user_input["council"] == "":
                errors["base"] = "council"

            # Check for errors
            if not errors:
                # Input is valid, set data
                user_input["council"] = self.council_names[
                    self.council_options.index(user_input["council"])
                ]
                self.data = user_input
                _LOGGER.info(LOG_PREFIX + "User input: %s", user_input)
                # Return the form of the next step
                return await self.async_step_council()

        # Show the configuration form to the user with the dropdown for the "council" field
        _LOGGER.info(
            LOG_PREFIX + "Showing user form with options: %s", self.council_options
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=""): cv.string,
                    vol.Required("council", default=""): vol.In(self.council_options),
                }
            ),
            errors=errors,
        )

    async def async_step_council(self, user_input=None):
        """Second step to configure the council details."""
        errors = {}

        if user_input is not None:
            # Set additional options
            if "SKIP_GET_URL" in self.councils_data[self.data["council"]]:
                user_input["skip_get_url"] = True
                user_input["url"] = self.councils_data[self.data["council"]]["url"]

            # Save the selected council in the user input
            user_input["name"] = "{}".format(self.data["name"])
            user_input["council"] = self.data["council"]

            # Create the config entry
            _LOGGER.info(LOG_PREFIX + "Creating config entry with data: %s", user_input)
            return self.async_create_entry(
                title=user_input["name"], data=user_input
            )

        # Show the configuration form to the user with the specific councils necessary fields
        council_schema = await self.get_council_schema(self.data["council"])
        _LOGGER.info(
            LOG_PREFIX + "Showing council form with schema: %s", council_schema
        )
        return self.async_show_form(
            step_id="council", data_schema=council_schema, errors=errors
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow initiated by the user."""
        _LOGGER.info(LOG_PREFIX + "Initiating flow with user input: %s", user_input)
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry,
    ) -> config_entries.OptionsFlow:
        _LOGGER.info(LOG_PREFIX + "Options flow config_entry: %s", config_entry)
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None) -> None:
        """Manage the options."""
        if user_input is not None:
            _LOGGER.info(LOG_PREFIX + "Options flow user input: %s", user_input)
            return self.async_create_entry(title="", data=user_input)

        # Access the data from the config_entry parameter
        council_data = self.config_entry.data
        council_schema = await UkBinCollectionConfigFlow().get_council_schema(
            council_data["council"]
        )

        _LOGGER.info(
            LOG_PREFIX + "Showing options form with schema: %s", council_schema
        )
        return self.async_show_form(step_id="council", data_schema=council_schema)
