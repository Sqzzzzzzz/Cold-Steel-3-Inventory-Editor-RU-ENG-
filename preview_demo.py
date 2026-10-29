"""Explicit, isolated UI demo. All example data and edits live in memory.

Normal application startup never imports this module. The temporary sample
save is synthetic, is not playable, and cannot be exported through this mode.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
import tempfile

from cs3_save import CS3Save, SAVE_SIZE, TABLE_OFFSET, TABLE_END, RECORD_SIZE, RECORD_COUNT, EMPTY_ID
from qt_backend import EditorCore


def demo_catalog():
    from game_icons import MASTER_QUARTZ_NAMES
    translated=['Бригид','Скульд','Сириус','Дева','Канон','Регулус','Зефир','Калейдо',
                'Оберон','Мёбиус','София','Хранитель','Титания','Мрак','Катце','Вирго',
                'Скорпион','Дюнамис','Темпест','Эгида','Тор','Беовульф','Минотавр',
                'Пандора','Эмблема','Магиус','Шевалье','Гунгнир','Регалия','Вальхалла']
    records={};english={}
    elements=['space']*5+['water','mirage','space','fire','wind','wind','mirage','mirage','time']
    for i,name in MASTER_QUARTZ_NAMES.items():
        base=i if i<3240 else {'Kaleido':3207,'Moebius':3209,'Gloom':3213,'Katze':3214,'Beowulf':3221,'Emblem':3224,'Chevalier':3226,'Aegis':3219}[name]
        ru=translated[base-3200]+(' EX' if i>=3240 or i in (3228,3229) else '')
        records[i]={'id':i,'name':ru,'category':'quartz_master',
                    'description':'Мастер-кварц. Пример описания для проверки интерфейса.',
                    'element':elements[(base-3200)%len(elements)],'_demo':True}
        english[i]={**records[i],'name':name+(' EX' if i>=3240 or i in (3228,3229) else ''),
                    'description':'Master quartz. Sample text for interface preview.'}
    records[3207]['description']='Мастер-кварц, обладающий\nмногогранной силой.\n\nЕго называют «калейдоскопом»,\nведь он способен раскрываться\nпо-разному в зависимости\nот владельца.\n\nДемонстрационный текст для проверки\nоформления и прокрутки описания.'
    english[3207]['description']='A master quartz with many facets.\n\nIts power reveals itself differently\ndepending on the person who wields it.\n\nSample text for the interface preview.'
    # Curated real IDs and RU/EN names; synthetic quantities stay isolated.
    families=[
        ('quartz_normal',(3350, 3351, 3352, 3353, 3354, 3355, 3356, 3357, 3358, 3359, 3360, 3361),
         ['Алмазная нова', 'Слеза', 'Слеза-ра', 'Слеза-рал', 'Курия', 'Телас', 'Ателас', 'HP 1', 'Щит 1', 'Немота', 'Заморозка', 'Разрушитель духа'],
         ['Diamond Nova', 'Tear', 'Teara', 'Tearal', 'Curia', 'Thelas', 'Athelas', 'HP 1', 'Shield 1', 'Mute', 'Freeze', 'Spirit Breaker']),
        ('weapon',(1200, 1215, 1230),
         ['Хиэн', 'Миротворец', 'Многослойные клинки'],
         ['Hien', 'Peacemaker', 'Layer Edges']),
        ('armor',(420, 421, 422),
         ['Золотая куртка', 'Серебряная роба', 'Регалии Улисса'],
         ['Gold Jacket', 'Silver Robe', 'Ulysses Regalia']),
        ('shoes',(500, 501, 502),
         ['Кожаные ботинки', 'Лёгкая обувь', 'Белая кожа'],
         ['Leather Boots', 'Light Shoes', 'White Leather']),
        ('accessory',(600, 601, 602),
         ['Серебряная серьга', 'Серебряная цепь', 'Серебряный амулет'],
         ['Silver Earring', 'Silver Chain', 'Silver Charm']),
        ('consumable',(20, 21, 0),
         ['Благовоние духа', 'Благовоние дракона', 'Целебный бальзам'],
         ['Spirit Incense', 'Dragon Incense', 'Tear Balm']),
        ('food',(3022, 3023, 3024),
         ['Картофельный салат', 'Горка луковых колец', 'Воздушный шифоновый торт'],
         ['Chunky Potato Salad', 'Piled Onion Rings', 'Fluffy Chiffon Cake']),
        ('ingredient',(3100, 3101, 3102),
         ['Свежее яйцо', 'Свежее молоко', 'Выдержанный сыр'],
         ['Fresh Egg', 'Fresh Milk', 'Mature Cheese']),
        ('recipe',(2340, 2341),
         ['Мужская кухня - Картофельный салат', 'Мужская кухня - Лук'],
         ['Manly Munchies - Potato Salad', 'Manly Munchies - Onions']),
        ('book',(260, 261),
         ['Имперская Хроника - Выпуск 1', 'Имперская Хроника - Выпуск 2'],
         ['Imperial Chronicle - Issue 1', 'Imperial Chronicle - Issue 2']),
        ('material',(60,),
         ['U-материал'],
         ['U-Material']),
    ]
    for cat,ids,ru,en in families:
        for i,name,translation in zip(ids,ru,en):
            records[i]={'id':i,'name':name,'category':cat,
                'description':'Образец данных для демонстрации интерфейса.','_demo':True}
            english[i]={**records[i],'name':translation,'description':'Sample data for the interface preview.'}
    return records,english


def synthetic_demo_save():
    data=bytearray(SAVE_SIZE)
    data[:8]=bytes.fromhex('02 00 00 00 01 00 00 00');data[8:12]=SAVE_SIZE.to_bytes(4,'little')
    data[TABLE_OFFSET:TABLE_END]=(EMPTY_ID.to_bytes(2,'little')+bytes(RECORD_SIZE-2))*RECORD_COUNT
    entries=[(3200,1),(3201,1),(3202,1),(3207,1),(3209,1),(3212,1),(3215,1),
             (3217,1),(3220,1),(3223,1),(3227,1),(3350,2),(3354,3),
             (20,15),(21,8),(60,24),(1200,1),(420,2),(500,2),(600,1),(3022,6),(3100,12)]
    for slot,(i,qty) in enumerate(entries):
        at=TABLE_OFFSET+slot*RECORD_SIZE;data[at:at+4]=i.to_bytes(2,'little')+qty.to_bytes(2,'little')
    return bytes(data)


class DemoCore(EditorCore):
    demo_mode=True
    def __init__(self):
        self.settings={'auto_latest':False,'language':'ru'};self.language='ru'
        self.favorites=set();self.recent=[];self.undo_stack=deque(maxlen=20);self.last_scan=None
        self.base,self.english=demo_catalog();self.overrides={};self.rebuild_catalog()
        self._temporary=tempfile.TemporaryDirectory(prefix='cs3-ui-demo-')
        self.source=Path(self._temporary.name)/'save016.dat';self.save=CS3Save(synthetic_demo_save())
        self.source.write_bytes(self.save.bytes())

    def set_language(self,language):
        if language not in ('ru','en'):raise ValueError(language)
        self.language=language;self.settings['language']=language

    def persist_lists(self):
        pass

    def _unavailable(self,*args,**kwargs):
        raise RuntimeError('Демонстрационный режим: запусти обычную версию для работы со своими файлами.\nDemo mode: start the normal editor to work with your own files.')

    latest=open_file=save_copy=overwrite_with_backup=scan_game=apply_scan_result=import_english_catalog=_unavailable

    def cleanup(self):
        self._temporary.cleanup()


def create_demo_window():
    from qt_window import MainWindow
    class DemoWindow(MainWindow):
        def initial_load(self):
            pass

        def scan_game(self,*args,**kwargs):
            self.scan_state.setText(self.msg('Демонстрационный режим','Demonstration mode'))

    window=DemoWindow(DemoCore())
    window.filter_group='quartz_master';window.populate_categories();window.update_tables()
    for row in range(window.cat_table.rowCount()):
        from PySide6.QtCore import Qt
        if window.cat_table.item(row,0).data(Qt.ItemDataRole.UserRole)==3207:
            window.cat_table.selectRow(row);break
    return window
