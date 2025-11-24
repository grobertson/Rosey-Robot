"""
Unit tests for subject hierarchy
"""
import pytest

from bot.rosey.core.subjects import (
    Subjects,
    EventTypes,
    SubjectBuilder,
    build_platform_subject,
    build_command_subject,
    build_plugin_subject,
    plugin_command,
    plugin_event,
    validate,
    parse,
    matches_pattern,
)


class TestSubjects:
    """Test Subjects constants"""

    def test_base_subject(self):
        """Test base subject constant"""
        assert Subjects.BASE == "rosey"

    def test_platform_subject(self):
        """Test platform subject pattern"""
        assert Subjects.PLATFORM == "rosey.platform"

    def test_events_subject(self):
        """Test events subject pattern"""
        assert Subjects.EVENTS == "rosey.events"

    def test_commands_subject(self):
        """Test commands subject pattern"""
        assert Subjects.COMMANDS == "rosey.commands"

    def test_plugins_subject(self):
        """Test plugins subject pattern"""
        assert Subjects.PLUGINS == "rosey.plugins"

    def test_mediacms_subject(self):
        """Test mediacms subject pattern"""
        assert Subjects.MEDIACMS == "rosey.mediacms"

    def test_api_subject(self):
        """Test API subject pattern"""
        assert Subjects.API == "rosey.api"

    def test_security_subject(self):
        """Test security subject pattern"""
        assert Subjects.SECURITY == "rosey.security"

    def test_monitoring_subject(self):
        """Test monitoring subject pattern"""
        assert Subjects.MONITORING == "rosey.monitoring"

    def test_platform_subject_helper(self):
        """Test platform_subject helper method"""
        subject = Subjects.platform_subject("cytube", "message")
        assert subject == "rosey.platform.cytube.message"

    def test_event_subject_helper(self):
        """Test event_subject helper method"""
        subject = Subjects.event_subject("message")
        assert subject == "rosey.events.message"

    def test_command_subject_helper(self):
        """Test command_subject helper method"""
        subject = Subjects.command_subject("trivia", "execute")
        assert subject == "rosey.commands.trivia.execute"

    def test_plugin_subject_helper(self):
        """Test plugin_subject helper method"""
        subject = Subjects.plugin_subject("markov", "ready")
        assert subject == "rosey.plugins.markov.ready"

    def test_monitoring_subject_helper(self):
        """Test monitoring_subject helper method"""
        subject = Subjects.monitoring_subject("health")
        assert subject == "rosey.monitoring.health"


class TestEventTypes:
    """Test EventTypes constants"""

    def test_user_events(self):
        """Test user event constants"""
        assert EventTypes.USER_JOIN == "user.join"
        assert EventTypes.USER_LEAVE == "user.leave"
        assert EventTypes.USER_UPDATE == "user.update"

    def test_message_events(self):
        """Test message event constants"""
        assert EventTypes.MESSAGE == "message"
        assert EventTypes.MESSAGE_DELETE == "message.delete"
        assert EventTypes.MESSAGE_EDIT == "message.edit"

    def test_media_events(self):
        """Test media event constants"""
        assert EventTypes.MEDIA_CHANGE == "media.change"
        assert EventTypes.MEDIA_QUEUE == "media.queue"
        assert EventTypes.MEDIA_DELETE == "media.delete"

    def test_playlist_events(self):
        """Test playlist event constants"""
        assert EventTypes.PLAYLIST_ADD == "playlist.add"
        assert EventTypes.PLAYLIST_REMOVE == "playlist.remove"
        assert EventTypes.PLAYLIST_MOVE == "playlist.move"

    def test_command_events(self):
        """Test command event constants"""
        assert EventTypes.COMMAND == "command"
        assert EventTypes.COMMAND_RESULT == "command.result"
        assert EventTypes.COMMAND_ERROR == "command.error"

    def test_plugin_events(self):
        """Test plugin lifecycle constants"""
        assert EventTypes.PLUGIN_START == "plugin.start"
        assert EventTypes.PLUGIN_STOP == "plugin.stop"
        assert EventTypes.PLUGIN_ERROR == "plugin.error"
        assert EventTypes.PLUGIN_READY == "plugin.ready"

    def test_health_events(self):
        """Test health event constants"""
        assert EventTypes.HEALTH_CHECK == "health.check"
        assert EventTypes.HEALTH_STATUS == "health.status"


class TestSubjectBuilder:
    """Test SubjectBuilder class"""

    def test_build_platform_subject(self):
        """Test building platform subject"""
        subject = (SubjectBuilder()
                   .platform("cytube")
                   .event("message")
                   .build())

        assert subject == "rosey.platform.cytube.message"

    def test_build_command_subject(self):
        """Test building command subject"""
        subject = (SubjectBuilder()
                   .command("trivia", "answer")
                   .build())

        assert subject == "rosey.commands.trivia.answer"

    def test_build_plugin_subject(self):
        """Test building plugin subject"""
        subject = (SubjectBuilder()
                   .plugin("markov")
                   .event("ready")
                   .build())

        assert subject == "rosey.plugins.markov.ready"

    def test_builder_chaining(self):
        """Test method chaining returns self"""
        builder = SubjectBuilder()
        result = builder.platform("discord").event("user.join")

        assert result is builder  # Should return self
        assert builder.build() == "rosey.platform.discord.user.join"

    def test_builder_reset(self):
        """Test resetting builder"""
        builder = SubjectBuilder()
        builder.platform("cytube").event("message")

        builder.reset()
        subject = builder.commands().part("test").part("action").build()

        assert subject == "rosey.commands.test.action"

    def test_events_category(self):
        """Test events category builder"""
        subject = (SubjectBuilder()
                   .events()
                   .event("message")
                   .build())

        assert subject == "rosey.events.message"

    def test_commands_category(self):
        """Test commands category builder"""
        subject = (SubjectBuilder()
                   .commands()
                   .part("test")
                   .part("execute")
                   .build())

        assert subject == "rosey.commands.test.execute"

    def test_plugins_category(self):
        """Test plugins category builder"""
        subject = (SubjectBuilder()
                   .plugins()
                   .part("test")
                   .event("ready")
                   .build())

        assert subject == "rosey.plugins.test.ready"

    def test_monitoring_category(self):
        """Test monitoring category builder"""
        subject = (SubjectBuilder()
                   .monitoring()
                   .part("health")
                   .build())

        assert subject == "rosey.monitoring.health"

    def test_security_category(self):
        """Test security category builder"""
        subject = (SubjectBuilder()
                   .security()
                   .part("violation")
                   .build())

        assert subject == "rosey.security.violation"

    def test_arbitrary_parts(self):
        """Test adding arbitrary parts"""
        subject = (SubjectBuilder()
                   .part("custom")
                   .part("subject")
                   .part("path")
                   .build())

        assert subject == "rosey.custom.subject.path"


class TestSubjectHelpers:
    """Test helper functions"""

    def test_build_platform_subject_helper(self):
        """Test build_platform_subject helper"""
        subject = build_platform_subject("slack", "message")
        assert subject == "rosey.platform.slack.message"

    def test_build_command_subject_helper(self):
        """Test build_command_subject helper"""
        subject = build_command_subject("calendar", "create")
        assert subject == "rosey.commands.calendar.create"

    def test_build_plugin_subject_helper(self):
        """Test build_plugin_subject helper"""
        subject = build_plugin_subject("echo", "error")
        assert subject == "rosey.plugins.echo.error"

    def test_plugin_command_helper(self):
        """Test plugin_command helper"""
        pattern = plugin_command("trivia")
        assert pattern == "rosey.commands.trivia.>"

    def test_plugin_event_helper(self):
        """Test plugin_event helper"""
        pattern = plugin_event("markov")
        assert pattern == "rosey.plugins.markov.>"


class TestSubjectValidation:
    """Test subject validation"""

    def test_validate_valid_platform_subject(self):
        """Test validating valid platform subject"""
        assert validate("rosey.platform.cytube.message")

    def test_validate_valid_events_subject(self):
        """Test validating valid events subject"""
        assert validate("rosey.events.message")

    def test_validate_valid_command_subject(self):
        """Test validating valid command subject"""
        assert validate("rosey.commands.trivia.answer")

    def test_validate_wildcard_star(self):
        """Test validating wildcard with *"""
        assert validate("rosey.platform.*")
        assert validate("rosey.events.*")
        assert validate("rosey.commands.*.*")

    def test_validate_wildcard_greater(self):
        """Test validating wildcard with >"""
        assert validate("rosey.events.>")
        assert validate("rosey.commands.trivia.>")

    def test_validate_invalid_empty(self):
        """Test validating empty subject"""
        assert not validate("")

    def test_validate_invalid_no_base(self):
        """Test validating subject without base"""
        assert not validate("invalid")
        assert not validate("platform.cytube.message")

    def test_validate_invalid_double_dot(self):
        """Test validating subject with empty part"""
        assert not validate("rosey..invalid")
        assert not validate("rosey.platform..message")

    def test_validate_invalid_leading_dot(self):
        """Test validating subject with leading dot"""
        assert not validate(".rosey.platform")

    def test_validate_invalid_trailing_dot(self):
        """Test validating subject with trailing dot"""
        assert not validate("rosey.platform.")

    def test_validate_invalid_greater_not_at_end(self):
        """Test validating > not at end"""
        assert not validate("rosey.>.platform")
        assert not validate("rosey.commands.>.test")

    def test_validate_too_short(self):
        """Test validating too short subject"""
        assert not validate("rosey")


class TestSubjectParsing:
    """Test subject parsing"""

    def test_parse_platform_subject(self):
        """Test parsing platform subject"""
        parts = parse("rosey.platform.cytube.message")

        assert parts["base"] == "rosey"
        assert parts["category"] == "platform"
        assert parts["platform"] == "cytube"
        assert parts["event"] == "message"

    def test_parse_platform_subject_with_dots(self):
        """Test parsing platform subject with dots in event"""
        parts = parse("rosey.platform.discord.user.join")

        assert parts["platform"] == "discord"
        assert parts["event"] == "user.join"

    def test_parse_events_subject(self):
        """Test parsing events subject"""
        parts = parse("rosey.events.message")

        assert parts["category"] == "events"
        assert parts["event"] == "message"

    def test_parse_events_subject_with_dots(self):
        """Test parsing events subject with dots"""
        parts = parse("rosey.events.user.join")

        assert parts["event"] == "user.join"

    def test_parse_command_subject(self):
        """Test parsing command subject"""
        parts = parse("rosey.commands.trivia.answer")

        assert parts["category"] == "commands"
        assert parts["plugin"] == "trivia"
        assert parts["action"] == "answer"

    def test_parse_plugin_subject(self):
        """Test parsing plugin subject"""
        parts = parse("rosey.plugins.markov.ready")

        assert parts["category"] == "plugins"
        assert parts["plugin"] == "markov"
        assert parts["event"] == "ready"

    def test_parse_monitoring_subject(self):
        """Test parsing monitoring subject"""
        parts = parse("rosey.monitoring.health.check")

        assert parts["category"] == "monitoring"
        assert parts["metric"] == "health.check"

    def test_parse_security_subject(self):
        """Test parsing security subject"""
        parts = parse("rosey.security.violation.detected")

        assert parts["category"] == "security"
        assert parts["event"] == "violation.detected"

    def test_parse_invalid_subject(self):
        """Test parsing invalid subject"""
        parts = parse("invalid.subject")

        assert parts == {}

    def test_parse_too_short(self):
        """Test parsing too short subject"""
        parts = parse("rosey")

        assert parts == {}


class TestWildcardMatching:
    """Test wildcard pattern matching"""

    def test_exact_match(self):
        """Test exact subject match"""
        assert matches_pattern(
            "rosey.platform.cytube.message",
            "rosey.platform.cytube.message"
        )

    def test_star_wildcard_single_token(self):
        """Test * wildcard matches single token"""
        assert matches_pattern(
            "rosey.platform.cytube.message",
            "rosey.platform.*.message"
        )

        assert matches_pattern(
            "rosey.platform.discord.message",
            "rosey.platform.*.message"
        )

    def test_star_wildcard_multiple(self):
        """Test multiple * wildcards"""
        assert matches_pattern(
            "rosey.platform.cytube.message",
            "rosey.platform.*.*"
        )

        assert matches_pattern(
            "rosey.commands.trivia.execute",
            "rosey.*.*.*"
        )

    def test_greater_wildcard_matches_rest(self):
        """Test > wildcard matches one or more tokens"""
        assert matches_pattern(
            "rosey.platform.cytube.message",
            "rosey.platform.>"
        )

        assert matches_pattern(
            "rosey.platform.cytube.user.join",
            "rosey.platform.>"
        )

        assert matches_pattern(
            "rosey.commands.trivia.answer",
            "rosey.commands.>"
        )

    def test_greater_with_prefix(self):
        """Test > wildcard with prefix"""
        assert matches_pattern(
            "rosey.commands.trivia.execute",
            "rosey.commands.trivia.>"
        )

        assert matches_pattern(
            "rosey.commands.trivia.answer.correct",
            "rosey.commands.trivia.>"
        )

    def test_no_match_different_prefix(self):
        """Test no match with different prefix"""
        assert not matches_pattern(
            "rosey.events.message",
            "rosey.commands.>"
        )

        assert not matches_pattern(
            "rosey.platform.discord.message",
            "rosey.platform.cytube.>"
        )

    def test_no_match_wrong_length(self):
        """Test no match with wrong token count"""
        assert not matches_pattern(
            "rosey.platform.cytube",
            "rosey.platform.*.message"
        )

        assert not matches_pattern(
            "rosey.platform.cytube.message.extra",
            "rosey.platform.*.message"
        )

    def test_star_and_greater_combination(self):
        """Test combining * and >"""
        assert matches_pattern(
            "rosey.platform.cytube.message",
            "rosey.*.>"
        )

        assert matches_pattern(
            "rosey.platform.discord.user.join",
            "rosey.*.>"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
