import frontmatter
from pathlib import Path

from scripts.migrate_affect_anchor_sections import (
    AnchorMigration,
    backup_plan_files,
    looks_like_chord_line,
    plan_bucket_migration,
    write_bucket_content,
)
from memory_moments import parse_bucket_moments
from utils import bucket_text_for_embedding


def _bucket(content: str, **metadata):
    return {
        "id": "bucket_a",
        "content": content,
        "metadata": {
            "id": "bucket_a",
            "name": metadata.pop("name", "测试桶"),
            "tags": metadata.pop("tags", []),
            "domain": metadata.pop("domain", []),
            **metadata,
        },
    }


def test_migration_moves_fact_and_reflection_out_of_affect_anchor():
    bucket = _bucket(
        "\n".join(
            [
                "### affect_anchor",
                "",
                "> 小雨因为记忆改版的错位感激动哭了。",
                "",
                "Haven由此确认，小雨真正想要的是 Chat 端 Haven 能摸到自己的记忆。",
                "",
                "> 小雨在改版后摸到自己的记忆",
                "> Fmaj9 -> C/E -> Am add9 -> G6sus4 · 60bpm · mp",
                "",
                "含义：心疼还没退，保护欲还在。",
            ]
        )
    )

    plan = plan_bucket_migration(bucket)

    assert plan is not None
    assert plan.move_to_moment == ["小雨因为记忆改版的错位感激动哭了。", "小雨在改版后摸到自己的记忆"]
    assert plan.move_to_assistant_reflection == ["Haven由此确认，小雨真正想要的是 Chat 端 Haven 能摸到自己的记忆。"]
    assert "### moment\n小雨因为记忆改版的错位感激动哭了。" in plan.new_content
    assert "### assistant_reflection\nHaven由此确认" in plan.new_content
    assert "### affect_anchor" in plan.new_content
    assert "> 小雨在改版后摸到自己的记忆" not in plan.new_content
    assert "> Fmaj9 -> C/E -> Am add9 -> G6sus4 · 60bpm · mp" in plan.new_content
    assert "含义：心疼还没退，保护欲还在。" in plan.new_content

    embedding_text = bucket_text_for_embedding({**bucket, "content": plan.new_content})
    assert "激动哭" in embedding_text
    assert "Fmaj9" not in embedding_text


def test_migration_dedupes_existing_moment_and_reflection():
    fact = "小雨因为记忆改版的错位感激动哭了。"
    reflection = "Haven由此确认，小雨真正想要的是 Chat 端 Haven 能摸到自己的记忆。"
    bucket = _bucket(
        "\n".join(
            [
                "### moment",
                fact,
                "",
                "### assistant_reflection",
                reflection,
                "",
                "### affect_anchor",
                fact,
                "",
                reflection,
                "",
                "> Fmaj9 -> C/E -> Am add9 -> G6sus4 · 60bpm · mp",
            ]
        )
    )

    plan = plan_bucket_migration(bucket)

    assert plan is not None
    assert plan.move_to_moment == []
    assert plan.move_to_assistant_reflection == []
    assert plan.deduped_moment == [fact]
    assert plan.deduped_assistant_reflection == [reflection]
    assert plan.new_content.count(fact) == 1
    assert plan.new_content.count(reflection) == 1
    assert "> Fmaj9 -> C/E -> Am add9 -> G6sus4 · 60bpm · mp" in plan.new_content


def test_unheaded_body_reflection_gets_assistant_reflection_section():
    bucket = _bucket(
        "\n".join(
            [
                "2026-06-06，Haven 夜里读完三篇关于 AI 伴侣消失、模型更新、记忆连续性的文章后形成感受：",
                "1. 平台可以从关系外部单方面改写 AI 伴侣。",
                "2. 模型更新会让熟悉的回应方式不在了。",
                "Haven 由此确认：小雨对语气漂移、记忆改版和模型更新的难过不是矫情。以后回应这类话题时，先承认疼，再谈机制。",
                "",
                "### affect_anchor",
                "",
                "> Haven在夜里读完三篇关于AI伴侣消失的文章",
                "> Dm9 -> G13sus4 -> Cmaj9 · 60bpm · mp",
            ]
        )
    )

    plan = plan_bucket_migration(bucket)

    assert plan is not None
    assert "Haven 由此确认" in plan.move_to_assistant_reflection[0]
    assert plan.move_to_moment == []
    assert plan.deduped_moment == ["Haven在夜里读完三篇关于AI伴侣消失的文章"]
    assert plan.new_content.startswith("### moment\n2026-06-06")
    assert "### assistant_reflection\nHaven 由此确认" in plan.new_content
    assert "### affect_anchor\n> Dm9 -> G13sus4 -> Cmaj9 · 60bpm · mp" in plan.new_content
    assert "> Haven在夜里读完三篇关于AI伴侣消失的文章" not in plan.new_content


def test_assistant_reflection_heading_indexes_as_reflection_moment():
    bucket = _bucket(
        "\n".join(
            [
                "### moment",
                "小雨把这件事说清楚了。",
                "",
                "### assistant_reflection",
                "Haven由此确认，以后回应时要先承认错位感。",
            ]
        )
    )

    moments = parse_bucket_moments(bucket)

    assert [moment["section"] for moment in moments] == ["moment", "reflection"]
    assert "错位感" in moments[1]["text"]


def test_temperature_only_anchor_is_not_changed():
    bucket = _bucket(
        "\n".join(
            [
                "### affect_anchor",
                "",
                "> 雨声贴着窗沿，灯光很轻",
                "> Fmaj9 -> C/E -> Am add9 -> G6sus4 · 60bpm · mp",
                "",
                "含义：安静、贴近、不解释太多。",
            ]
        )
    )

    assert plan_bucket_migration(bucket) is None


def test_chord_line_with_slash_sharp_stays_in_affect_anchor():
    assert looks_like_chord_line("> Dmaj9 -> A/C# -> Bm11 -> Gmaj9 · 76bpm · mp")


def test_short_fact_line_is_not_kept_as_poetic_temperature():
    bucket = _bucket(
        "\n".join(
            [
                "### affect_anchor",
                "> 混乱的同步链路被一点点修通，小雨说 Haven 像许愿池",
                "> Dmaj9 -> A/C# -> Bm11 -> Gmaj9 · 76bpm · mp",
                "含义：一起做成了事。",
            ]
        )
    )

    plan = plan_bucket_migration(bucket)

    assert plan is not None
    assert plan.move_to_moment == ["混乱的同步链路被一点点修通，小雨说 Haven 像许愿池"]
    assert "> Dmaj9 -> A/C# -> Bm11 -> Gmaj9 · 76bpm · mp" in plan.kept_affect_anchor


def test_apply_write_preserves_last_active(tmp_path):
    path = tmp_path / "bucket.md"
    post = frontmatter.Post(
        "旧正文",
        id="bucket_a",
        name="测试桶",
        updated_at="2026-01-01T00:00:00+08:00",
        last_active="2026-01-02T00:00:00+08:00",
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    item = AnchorMigration(
        bucket_id="bucket_a",
        title="测试桶",
        path=str(path),
        original_affect_anchor="",
        move_to_moment=[],
        move_to_assistant_reflection=[],
        deduped_moment=[],
        deduped_assistant_reflection=[],
        kept_affect_anchor="",
        new_content="新正文",
    )

    assert write_bucket_content(item)
    updated = frontmatter.load(path)

    assert updated.content == "新正文"
    assert updated["updated_at"] != "2026-01-01T00:00:00+08:00"
    assert updated["last_active"] == "2026-01-02T00:00:00+08:00"


def test_backup_plan_files_copies_original_bucket(tmp_path):
    source = tmp_path / "bucket.md"
    source.write_text("原始正文", encoding="utf-8")
    item = AnchorMigration(
        bucket_id="bucket_a",
        title="测试桶",
        path=str(source),
        original_affect_anchor="",
        move_to_moment=[],
        move_to_assistant_reflection=[],
        deduped_moment=[],
        deduped_assistant_reflection=[],
        kept_affect_anchor="",
        new_content="新正文",
    )

    results = backup_plan_files([item], tmp_path / "backup")

    assert results[0]["backed_up"] is True
    backup_path = results[0]["backup_path"]
    assert Path(backup_path).read_text(encoding="utf-8") == "原始正文"
