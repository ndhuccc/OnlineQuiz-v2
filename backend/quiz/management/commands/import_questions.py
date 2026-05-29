from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from quiz.services.import_json import import_from_json_text


class Command(BaseCommand):
    help = "從 questions.json 格式檔案匯入題庫"

    def add_arguments(self, parser):
        parser.add_argument("json_path", type=str, help="JSON 檔案路徑")
        parser.add_argument("--name", type=str, default=None, help="題庫名稱")
        parser.add_argument("--points", type=float, default=1.0, help="預設配分")
        parser.add_argument("--timer", type=int, default=90, help="預設作答秒數")

    def handle(self, *args, **options):
        path = Path(options["json_path"])
        if not path.exists():
            raise CommandError(f"找不到檔案：{path}")

        text = path.read_text(encoding="utf-8-sig")
        result = import_from_json_text(
            text,
            bank_name=options["name"] or path.stem,
            default_points=options["points"],
            default_timer_seconds=options["timer"],
        )

        if not result.success:
            for err in result.errors:
                self.stderr.write(f"  第 {err.index + 1} 題：{err.message}")
            raise CommandError("匯入失敗")

        self.stdout.write(
            self.style.SUCCESS(
                f"已匯入題庫「{result.bank_name}」(id={result.bank_id})，"
                f"共 {result.imported_count} 題"
            )
        )
        if result.errors:
            self.stdout.write(self.style.WARNING(f"另有 {len(result.errors)} 題失敗"))
