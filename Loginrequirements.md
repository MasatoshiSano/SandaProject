/production/line-select/で生産ラインを選択する際、ユーザーが選択できるライン（UserLineAccess）を登録していない場合は、
この画面に来る前に、UserLineAccessを登録する画面に遷移したい。
登録画面では、複数のラインを選択できるようにしたい。
ライン一覧は、Lineモデルで登録しておく。
Lineは、
1文字目でカテゴリ分けして表示する。
ボタンを押して、複数選べるようにしたい。
UserLineAccessでは、lineをline = models.ForeignKey(Line, on_delete=models.CASCADE, verbose_name='ライン')
これで管理する。admin画面も修正してください。
