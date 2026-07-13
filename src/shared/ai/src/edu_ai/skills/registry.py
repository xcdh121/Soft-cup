from edu_core.schemas.agent_skills import SkillDefinition


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, definition: SkillDefinition) -> None:
        if definition.skill_id in self._skills:
            raise ValueError(f"Skill already registered: {definition.skill_id}")
        self._skills[definition.skill_id] = definition

    def get(self, skill_id: str) -> SkillDefinition:
        try:
            skill = self._skills[skill_id]
        except KeyError as exc:
            raise KeyError(f"Unknown skill: {skill_id}") from exc
        if skill.status == "disabled":
            raise ValueError(f"Skill is disabled: {skill_id}")
        return skill

    def all(self) -> list[SkillDefinition]:
        return list(self._skills.values())
