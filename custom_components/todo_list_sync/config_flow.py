"""Config flow for Todo List Sync."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.todo import TodoListEntity
from homeassistant.components.todo.const import DATA_COMPONENT, TodoListEntityFeature
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CONFLICT_POLICY,
    CONF_PRIMARY_ENTITY,
    CONF_REFRESH_ON_RECONNECT,
    CONF_SECONDARY_ENTITY,
    CONF_VERIFICATION_INTERVAL,
    DEFAULT_CONFLICT_POLICY,
    DEFAULT_REFRESH_ON_RECONNECT,
    DEFAULT_VERIFICATION_INTERVAL,
    DOMAIN,
    MAX_VERIFICATION_INTERVAL,
    MIN_VERIFICATION_INTERVAL,
    VERIFICATION_STEP,
    ConflictPolicy,
)

_REQUIRED_FEATURES = (
    TodoListEntityFeature.CREATE_TODO_ITEM
    | TodoListEntityFeature.UPDATE_TODO_ITEM
    | TodoListEntityFeature.DELETE_TODO_ITEM
)


def _todo_selector() -> selector.EntitySelector:
    """Return an entity selector limited to to-do lists."""

    return selector.EntitySelector(selector.EntitySelectorConfig(domain="todo"))


def _entity_supports_sync(hass, entity_id: str) -> bool:
    """Return whether a loaded Todo entity supports the required CRUD features."""

    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        return False
    entity = component.get_entity(entity_id)
    if not isinstance(entity, TodoListEntity):
        return False
    supported = TodoListEntityFeature(entity.supported_features or 0)
    return supported & _REQUIRED_FEATURES == _REQUIRED_FEATURES


class TodoListSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Todo List Sync config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the two to-do lists."""

        errors: dict[str, str] = {}

        if user_input is not None:
            primary = user_input[CONF_PRIMARY_ENTITY]
            secondary = user_input[CONF_SECONDARY_ENTITY]

            if primary == secondary:
                errors["base"] = "same_entity"
            elif not _entity_supports_sync(self.hass, primary):
                errors[CONF_PRIMARY_ENTITY] = "unsupported_entity"
            elif not _entity_supports_sync(self.hass, secondary):
                errors[CONF_SECONDARY_ENTITY] = "unsupported_entity"
            else:
                selected = {primary, secondary}
                for entry in self._async_current_entries(include_ignore=False):
                    existing = {
                        entry.data.get(CONF_PRIMARY_ENTITY),
                        entry.data.get(CONF_SECONDARY_ENTITY),
                    }
                    if selected & existing:
                        errors["base"] = "entity_already_used"
                        break

            if not errors:
                await self.async_set_unique_id(f"{primary}|{secondary}")
                self._abort_if_unique_id_configured()
                primary_state = self.hass.states.get(primary)
                secondary_state = self.hass.states.get(secondary)
                primary_name = primary_state.name if primary_state else primary
                secondary_name = secondary_state.name if secondary_state else secondary
                return self.async_create_entry(
                    title=f"{primary_name} ↔ {secondary_name}",
                    data={
                        CONF_PRIMARY_ENTITY: primary,
                        CONF_SECONDARY_ENTITY: secondary,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_PRIMARY_ENTITY): _todo_selector(),
                vol.Required(CONF_SECONDARY_ENTITY): _todo_selector(),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""

        return TodoListSyncOptionsFlow()


class TodoListSyncOptionsFlow(OptionsFlowWithReload):
    """Configure synchronization behavior."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage integration options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONFLICT_POLICY,
                    default=options.get(CONF_CONFLICT_POLICY, DEFAULT_CONFLICT_POLICY),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            ConflictPolicy.PRIMARY.value,
                            ConflictPolicy.SECONDARY.value,
                        ],
                        translation_key="conflict_policy",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_VERIFICATION_INTERVAL,
                    default=options.get(
                        CONF_VERIFICATION_INTERVAL,
                        DEFAULT_VERIFICATION_INTERVAL,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_VERIFICATION_INTERVAL,
                        max=MAX_VERIFICATION_INTERVAL,
                        step=VERIFICATION_STEP,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
                vol.Required(
                    CONF_REFRESH_ON_RECONNECT,
                    default=options.get(
                        CONF_REFRESH_ON_RECONNECT,
                        DEFAULT_REFRESH_ON_RECONNECT,
                    ),
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
