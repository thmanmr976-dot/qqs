"""Launcher theme application, filtering, keyboard navigation and live reload."""
import re
import os
import subprocess
import shutil
import appearance
from pathlib import Path
from PySide6.QtCore import Qt,QSize,QTimer,QFileSystemWatcher,QEvent,QRectF
from PySide6.QtGui import QPixmap,QFont,QIcon,QShortcut,QKeySequence
from PySide6.QtWidgets import QListView,QMenu
from appearance import DEFAULTS
from ui_text import shortcut_hint,is_import_input


def matches(query,text,mode='substring',case_sensitive=False):
    if not case_sensitive:query,text=query.casefold(),text.casefold()
    if not query or mode=='disabled':return True
    if mode=='prefix':return text.startswith(query)
    if mode=='fuzzy':
        chars=iter(text);return all(any(c==wanted for c in chars) for wanted in query)
    return query in text


def padding(value):
    values=[int(p.removesuffix('px')) for p in str(value).split()]
    if len(values)==1:values=values*4
    elif len(values)==2:values=values*2
    elif len(values)==3:values=[values[0],values[1],values[2],values[1]]
    return values[3],values[0],values[1],values[2]


def css_padding(value,horizontal=False):
    if isinstance(value,int):return f'0 {value}px' if horizontal else f'{value}px'
    return ' '.join(p if p.endswith('px') else p+'px' for p in value.split())


class Customizable:
    def init_customization(self):
        self.grid_delay=QTimer(self);self.grid_delay.setSingleShot(True);self.grid_delay.timeout.connect(self.update_grid);self.list.viewport().installEventFilter(self)
        self.bound_keys=[];self.theme_reload=QTimer(self);self.theme_reload.setSingleShot(True);self.theme_reload.timeout.connect(lambda:self.reload_appearance(live=True) if self.isVisible() else None)
        self.theme_watcher=QFileSystemWatcher(self);self.theme_watcher.fileChanged.connect(self.queue_reload);self.theme_watcher.directoryChanged.connect(self.queue_reload)
        self.source.textChanged.connect(self.filter_rices)
    def queue_reload(self,*_):
        if self.isVisible() and self.theme.get('live_reload',True):self.theme_reload.start(180)
    def watch_themes(self):
        old=self.theme_watcher.files()+self.theme_watcher.directories()
        if old:self.theme_watcher.removePaths(old)
        paths=[appearance.CONFIG,DEFAULTS/'presets',*appearance.CONFIG.glob('*.rasi'),*appearance.CONFIG.glob('*.lua')]
        for group in appearance.THEME_FILES.values():paths.extend(group)
        for key in ('stylesheet_file','background_image','logo_file','row_icon_file'):
            if self.theme[key]:
                file=Path(self.theme[key]).expanduser();file=file if file.is_absolute() else appearance.CONFIG/file
                paths.extend((file,file.parent))
        paths=list(dict.fromkeys(paths))
        self.theme_watcher.addPaths([str(p) for p in paths if p.exists()])
    def configure_keys(self):
        for shortcut in self.bound_keys:shortcut.setEnabled(False);shortcut.deleteLater()
        self.bound_keys=[]
        actions={'keys_accept':self.handle_enter,'keys_next':lambda:self.move_selection(max(1,self.theme['list_columns'])),'keys_previous':lambda:self.move_selection(-max(1,self.theme['list_columns'])),'keys_close':self.hide,'keys_context':self.keyboard_context,'keys_add':self.add_source,'keys_reload':self.reload_appearance}
        for name,callback in actions.items():
            for sequence in re.split(r'[;,]',self.theme[name]):
                sequence=sequence.strip().replace('Control+','Ctrl+')
                if not sequence:continue
                key=QShortcut(QKeySequence(sequence),self);key.activated.connect(callback);self.bound_keys.append(key)
    def style_font(self,name):
        t=self.theme
        return QFont(t.get(name+'_font') or t['font'],t.get(name+'_font_size') or t['font_size'])
    def apply_customization(self):
        t=self.theme;screen=self.screen().availableGeometry()
        def dimension(value,total):return round(total*float(value[:-1])/100) if isinstance(value,str) and value.endswith('%') else value
        self.resize(min(screen.width(),max(320,dimension(t['width'],screen.width()))),min(screen.height(),max(200,dimension(t['height'],screen.height()))))
        self.background_pixmap=QPixmap()
        if t['background_image']:
            image=Path(t['background_image']).expanduser();image=image if image.is_absolute() else appearance.CONFIG/image
            self.background_pixmap=QPixmap(str(image))
            if self.background_pixmap.isNull():raise ValueError('Cannot load background image: '+str(image))
        self.logo.custom_image=bool(t['logo_file']);self.logo.image=QPixmap(str(Path(__file__).resolve().parent/'assets/logo.png'));self.logo.source_rect=QRectF(665,243,340,465)
        if t['logo_file']:
            file=Path(t['logo_file']).expanduser();file=file if file.is_absolute() else appearance.CONFIG/file
            self.logo.image=QPixmap(str(file));self.logo.source_rect=QRectF(self.logo.image.rect())
            if self.logo.image.isNull():raise ValueError('Cannot load logo image: '+str(file))
        self.row_icon=QIcon.fromTheme(t['row_icon_name'],QIcon(str(Path(__file__).resolve().parent/'assets/logo.png')))
        if t['row_icon_file']:
            file=Path(t['row_icon_file']).expanduser();file=file if file.is_absolute() else appearance.CONFIG/file
            self.row_icon=QIcon(str(file))
            if self.row_icon.isNull():raise ValueError('Cannot load row icon: '+str(file))
        self.setFont(QFont(t['font'],max(6,min(72,t['font_size']))))
        self.layout().setContentsMargins(*padding(t['layout_padding']));self.layout().setSpacing(t['layout_spacing']);self.input_layout.setSpacing(t['input_spacing'])
        self.source.setFixedHeight(max(20,t['input_height']));self.add.setFixedSize(max(30,t['button_width']),max(20,t['button_height']))
        self.source.setFont(self.style_font('input'));self.add.setFont(self.style_font('button'));self.list.setFont(self.style_font('row'))
        self.source.setToolTip('Type to filter saved rices. Paste a GitHub URL, folder, ZIP archive or shell entry file path to import.');self.add.setToolTip('Import the GitHub URL or local path entered above.');self.source.setPlaceholderText(t['placeholder']);self.add.setText(t['add_text']);self.add.setVisible(t['show_add_button'])
        self.title.setText(t['title_text']);self.title.setFont(self.style_font('title'));self.title.setVisible(t['show_title'])
        self.status.setText(shortcut_hint(t,self.source.text()) if t['footer_text']=='{shortcuts}' else t['footer_text']);self.status.setFont(self.style_font('footer'));self.footer_widget.setVisible(t['show_footer'])
        self.empty.setText(t['empty_text']);self.logo.background=t['background'];self.logo.setFixedSize(max(8,t['logo_size']),max(10,round(t['logo_size']*1.35)));self.logo.update();self.logo.setVisible(t['show_logo'])
        self.list.setSpacing(t['list_spacing']);self.list.setIconSize(QSize(t['icon_size'],t['icon_size']))
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if t['show_scrollbar'] else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if t['list_columns']>1:
            self.list.setViewMode(QListView.ViewMode.IconMode);self.list.setFlow(QListView.Flow.LeftToRight);self.list.setMovement(QListView.Movement.Static);self.list.setResizeMode(QListView.ResizeMode.Adjust);self.list.setWrapping(True)
        else:self.list.setViewMode(QListView.ViewMode.ListMode);self.list.setFlow(QListView.Flow.TopToBottom);self.list.setGridSize(QSize());self.list.setWrapping(False)
        order=[p.strip() for p in t['layout_order'].split(',')]
        if t['input_position']=='bottom':order.remove('input');order.insert(order.index('list')+1,'input')
        widgets={'title':self.title,'input':self.input_widget,'list':self.list,'footer':self.footer_widget}
        for key in order:
            self.layout().removeWidget(widgets[key]);self.layout().addWidget(widgets[key],1 if key=='list' else 0)
        self.layout().removeWidget(self.empty);self.layout().insertWidget(self.layout().indexOf(self.list)+1,self.empty)
        def color(key,fallback='text_color'):return t[key] or t[fallback]
        # IDs are public extension points for user Qt stylesheets.
        self.setStyleSheet(f'''
            QLabel {{color:{t['text_color']};background:transparent;}}
            QLabel#title {{color:{color('title_color')};}}
            QLabel#status {{color:{color('footer_color')};}}
            QLineEdit#entry {{color:{color('input_text_color')};background:{t['input_background']};border:{t['input_border_width']}px solid {t['input_border']};border-radius:{t['input_radius']}px;padding:{css_padding(t['input_padding'],True)};placeholder-text-color:{t['placeholder_color']};selection-color:{t['input_selection_color']};selection-background-color:{t['input_selection_background']};}}
            QLineEdit#entry:focus {{border-color:{t['border_color']};}}
            QPushButton#add {{background:{t['button_color']};color:{t['button_text_color']};border:0;border-radius:{t['button_radius']}px;}}
            QPushButton#add:hover {{background:{t['button_hover_color']};}}
            QPushButton#add:disabled {{background:#99abc3;}}
            QListWidget#riceList {{background:transparent;border:0;outline:0;color:{color('row_text_color')};}}
            QListWidget#riceList::item {{background:{t['row_background']};border:{t['row_border_width']}px solid {t['row_border']};border-radius:{t['row_radius']}px;padding:{css_padding(t['row_padding'],True)};}}
            QListWidget#riceList::item:alternate {{background:{t['row_alternate'] or t['row_background']};}}
            QListWidget#riceList::item:hover {{background:{t['row_hover']};}}
            QListWidget#riceList::item:selected {{background:{t['row_selected']};color:{color('row_selected_text_color')};border:{t['row_selected_border_width']}px solid {t['row_selected_border']};}}
            QScrollBar:vertical {{width:7px;background:transparent;}} QScrollBar::handle:vertical {{background:{t['input_border']};border-radius:3px;min-height:20px;}}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
            QMenu {{background:{t['background']};color:{t['text_color']};border:1px solid {t['border_color']};padding:6px;}}
            QMenu::item {{padding:8px 18px;}} QMenu::item:selected {{background:{t['row_selected']};}}
        '''+t['stylesheet']+self.extra_stylesheet())
        self.list.setAlternatingRowColors(bool(t['row_alternate']))
        self.configure_keys();self.watch_themes();self.update();self.update_grid()
    def extra_stylesheet(self):
        name=self.theme['stylesheet_file']
        if not name:return ''
        path=Path(name).expanduser()
        if not path.is_absolute():path=appearance.CONFIG/path
        return path.read_text(encoding='utf-8')
    def eventFilter(self,watched,event):
        if watched is self.list.viewport() and event.type()==QEvent.Type.Resize:self.grid_delay.start(0)
        return super().eventFilter(watched,event)
    def update_grid(self):
        if not hasattr(self,'list'):return
        t=self.theme;columns=max(1,min(12,t['list_columns']))
        width=max(45,(self.list.viewport().width()-(columns+1)*t['list_spacing']*2-8)//columns)
        if columns>1:self.list.setGridSize(QSize(width+2*t['list_spacing'],t['row_height']+2*t['list_spacing']))
        for i in range(self.list.count()):self.list.item(i).setSizeHint(QSize(width if columns>1 else 0,max(20,t['row_height'])))
        if t['list_lines']:
            self.list.setMaximumHeight(min(self.height(),max(1,t['list_lines'])*(t['row_height']+2*t['list_spacing'])))
        else:self.list.setMaximumHeight(16777215)
    def filter_rices(self,*_):
        if not hasattr(self,'empty'):return
        t=self.theme;query=self.source.text().strip();visible=[]
        # Pasted import sources should leave the existing collection visible.
        if query.startswith(('https://','http://','/','~','file://')):query=''
        for i in range(self.list.count()):
            item=self.list.item(i);rice=item.data(Qt.ItemDataRole.UserRole)
            fields={'name':rice['name'],'source':rice.get('source',''),'path':rice['entry']}
            texts=[fields.get(k.strip(),'') for k in t['search_fields'].split(',')]
            show=any(matches(query,text,t['search_mode'],t['search_case_sensitive']) for text in texts);item.setHidden(not show)
            if show:visible.append(item)
        current=self.list.currentItem()
        if visible and (current is None or current.isHidden()):self.list.setCurrentItem(visible[0])
        self.empty.setVisible(not visible);self.empty.setText('No saved rices match your search.' if query and not visible else t['empty_text'])
        if t['footer_text']=='{shortcuts}':self.status.setText(shortcut_hint(t,self.source.text()))
    def move_selection(self,delta):
        items=[self.list.item(i) for i in range(self.list.count()) if not self.list.item(i).isHidden()]
        if not items:return
        current=self.list.currentItem();index=items.index(current) if current in items else (-1 if delta>0 else 0)
        target=(index+delta)%len(items) if self.theme['navigation_wrap'] else max(0,min(len(items)-1,index+delta))
        self.list.setCurrentItem(items[target]);self.list.scrollToItem(items[target])
    def handle_enter(self):
        query=self.source.text().strip()
        if is_import_input(query):self.add_source();return
        item=self.list.currentItem()
        if item is not None and not item.isHidden():self.select_rice(item)
        elif query:self.status.setText('No saved rices match. Paste a GitHub URL or local path to import a rice.')
    def keyboard_context(self):
        item=self.list.currentItem()
        if item is not None and not item.isHidden():self.rice_actions(item.data(Qt.ItemDataRole.UserRole)).exec(self.list.viewport().mapToGlobal(self.list.visualItemRect(item).bottomLeft()))
    def position_popup(self):
        screen=self.screen().availableGeometry();t=self.theme;position=t['window_position']
        x=screen.center().x()-self.width()//2;y=screen.center().y()-self.height()//2
        if 'west' in position:x=screen.left()
        elif 'east' in position:x=screen.right()-self.width()+1
        if 'north' in position:y=screen.top()
        elif 'south' in position:y=screen.bottom()-self.height()+1
        x+=t['window_offset_x'];y+=t['window_offset_y']
        x=max(screen.left(),min(screen.right()-self.width()+1,x));y=max(screen.top(),min(screen.bottom()-self.height()+1,y))
        self.move(x,y)
        if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') and os.environ.get('QT_QPA_PLATFORM')!='offscreen' and shutil.which('hyprctl'):
            def move_on_compositor():
                if not self.isVisible():return
                code='for _,w in ipairs(hl.get_windows({class="qqs"})) do if w.pid=='+str(os.getpid())+' and w.title=="qqs — Quick Quick Shell" then hl.dispatch(hl.dsp.window.move({x='+str(x)+',y='+str(y)+',relative=false,window=w})) end end'
                try:subprocess.run(['hyprctl','eval',code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=.7)
                except (OSError,subprocess.TimeoutExpired):pass
            QTimer.singleShot(50,move_on_compositor)
