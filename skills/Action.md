# Xenith Action Skill

You are generating implementations for the XenithLibrary Action system.

Actions are runtime executable logic triggered by game events.

---

# CORE ARCHITECTURE

All actions must:

- Extend `AbstractAction`
- Implement:
  - `execute(ActionContext context)`
  - `serialize()`
  - `applyEdit(String field, String value)`
  - `fromConfig(DomainConfig config)` (static factory)

---

# EXECUTION RULES

## execute(ActionContext context)

- Always check:
  - `rolledSuccessfully()` first
  - `context.getPlayer()` may be null → must guard it

- Context usage:
  - Player → `context.getPlayer()`
  - Location → `context.resolveLocation()`
  - Persistent data → `context.getData()`

---

# PLACEHOLDERS

If PlaceholderAPI is enabled:

```java
XenithLibrary.isPapiEnabled()

PlaceholderAPI.setPlaceholders(player, message)
```
TEXT UTILITIES

All player-facing messages must be:

```java
Chat.colorize(text)
```

Example
```java
public class ExampleAction extends AbstractAction {

    private String value;

    public ExampleAction(String value) {
        this.value = value;
    }

    @Override
    public void execute(ActionContext context) {
        if (!rolledSuccessfully()) return;
        if (context.getPlayer() == null) return;

        context.getPlayer().sendMessage(
            Chat.colorize(value)
        );
    }

    @Override
    public Map<String, Object> serialize() {
        Map<String, Object> data =
            new LinkedHashMap<>(super.serialize());

        data.put("value", value);
        return data;
    }

    @Override
    public void applyEdit(String field, String value) {
        switch (field) {
            case "value" -> this.value = value;
            default -> super.applyEdit(field, value);
        }
    }

    public static AbstractAction fromConfig(DomainConfig config) {
        String value = config.getString("value", "");

        ExampleAction action = new ExampleAction(value);
        action.setChance(config.getDouble("chance", 100.0));

        return action;
    }
}
```

Return ONLY code in this format:

ALL ACTION IMPLEMENTATIONS GO UNDER THIS PATH:
<file path="src/main/java/me/ogali/xenithlibrary/actions/impl/YourAction.java"> ...java code... </file>

No explanations.
No markdown.
No commentary.
