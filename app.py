#!/usr/bin/env python3
"""qqs: a single-field rice launcher with an independent loading screen."""
import json
import hashlib
import appearance
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path
from PySide6.QtCore import Qt, QLocale, QThread, Signal, QTimer, QRectF, QPointF, QSize, QUrl, QDir, QFile, QEvent
from PySide6.QtGui import (QColor, QFont, QIcon, QPainter, QPainterPath, QLinearGradient, QRadialGradient, QPixmap, QFontMetrics, QPen, QDesktopServices, QShortcut, QKeySequence)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QLabel, QDialog, QPlainTextEdit, QMessageBox, QMenu, QFileDialog, QInputDialog, QFileSystemModel, QTreeView, QSplitter)
from core import download, extract_archive
from library import resolve_source, entry_files, source_metadata, infer_legacy_source, rice_folder
from runtime import Runtime, write_json, launch_environment
from appearance import load_theme, CONFIG
from customization import Customizable
from ui_text import source_action,startup_failure
from backends import NAMES,backend_for,launch_plan,eww_windows
from launchers import integrations,item_plan,dependency_report,prepare_bindings

BASE=Path(__file__).resolve().parent
DATA=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'quickshell-studio'

def quickshell_binary():
    return shutil.which('quickshell') or shutil.which('qs')

class ImportJob(QThread):
    done=Signal(str,str,dict)
    failed=Signal(str)
    def __init__(self, text, data):
        super().__init__(); self.text=text; self.data=data
    def run(self):
        try:
            kind, source, name=resolve_source(self.text)
            if kind=='github':
                with tempfile.TemporaryDirectory() as tmp:
                    archive=Path(tmp)/(name+'.zip'); download(source,archive)
                    root=extract_archive(archive,self.data/'interfaces')
            elif kind=='zip': root=extract_archive(source,self.data/'interfaces')
            else: root=Path(source)
            entry_files(root)
            self.done.emit(str(root),name,source_metadata(self.text))
        except Exception:
            self.failed.emit(traceback.format_exc())

class Logo(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedSize(38,52); self.background='#eaf4ff';self.custom_image=False;self.source_rect=QRectF(665,243,340,465); self.image=QPixmap(str(BASE/'assets/logo.png'))
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # Blend the supplied logo background into the panel.
        p.fillRect(self.rect(),QColor(self.background))
        if not self.custom_image:p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        p.drawPixmap(QRectF(1,1,self.width()-2,self.height()-2),self.image,self.source_rect)

class SegmentBar(QWidget):
    def __init__(self,theme):
        super().__init__(); self.theme=theme; self.step=0
        self.timer=QTimer(self); self.timer.timeout.connect(self.advance)
        self.timer.start(max(30,theme['animation_interval_ms']))
        self.setMinimumHeight(max(12,min(100,theme['segment_height']))+10)
    def advance(self):
        self.step=(self.step+1)%(max(4,min(40,self.theme['segments']))+1); self.update()
    def paintEvent(self,event):
        t=self.theme; count=max(4,min(40,t['segments'])); gap=min(30,t['segment_gap'])
        width=min(max(8,t['segment_width']),max(8,(self.width()-(count-1)*gap)/count))
        height=min(100,max(8,t['segment_height'])); total=count*width+(count-1)*gap
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if t['bar_style']=='line':
            rect=QRectF(4,(self.height()-height)/2,self.width()-8,height);p.setPen(QPen(QColor(t['bar_border_color']),t['bar_border_width']));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(rect,t['bar_radius'],t['bar_radius']);p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(t['bar_color']));rect.setWidth(rect.width()*self.step/count);p.drawRoundedRect(rect,t['bar_radius'],t['bar_radius']);return
        p.setPen(QPen(QColor(t['bar_border_color']),max(1,min(12,t['bar_border_width']))))
        for i in range(count):
            p.setBrush(QColor(t['bar_color']) if i<self.step else Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF((self.width()-total)/2+i*(width+gap),(self.height()-height)/2,width,height),t['bar_radius'],t['bar_radius'])

class LoadingText(QLabel):
    def __init__(self,text,theme,size):
        super().__init__(text); self.theme=theme
        self.setAlignment({'left':Qt.AlignmentFlag.AlignLeft,'center':Qt.AlignmentFlag.AlignHCenter,'right':Qt.AlignmentFlag.AlignRight}.get(theme.get('message_alignment','center'))|Qt.AlignmentFlag.AlignVCenter); self.setFont(QFont(theme['font'],size)); self.setMinimumHeight(size*2)
    def paintEvent(self,event):
        if not self.theme['pixelated_text']:
            super().paintEvent(event); return
        font=QFont(self.theme['font']); font.setPixelSize(12); font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        metrics=QFontMetrics(font); small=QPixmap(max(1,metrics.horizontalAdvance(self.text())+6),metrics.height()+4); small.fill(Qt.GlobalColor.transparent)
        p=QPainter(small);p.setFont(font);p.setPen(QColor(self.theme['text_color']));p.drawText(3,metrics.ascent()+2,self.text());p.end()
        scale=max(1,round(self.font().pointSizeF()/9)); width=small.width()*scale; height=small.height()*scale
        if width>self.width(): height=height*self.width()/width;width=self.width()
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,False)
        alignment=self.theme.get('message_alignment','center');x=0 if alignment=='left' else self.width()-width if alignment=='right' else (self.width()-width)/2
        p.drawPixmap(QRectF(x,(self.height()-height)/2,width,height),small,QRectF(small.rect()))

class Loading(QWidget):
    def __init__(self,theme):
        super().__init__(None,Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
        self.theme=theme;self.image=QPixmap()
        if theme['background_image']:
            file=Path(theme['background_image']).expanduser();file=file if file.is_absolute() else appearance.CONFIG/file
            self.image=QPixmap(str(file))
            if self.image.isNull():raise ValueError('Cannot load loading background: '+str(file))
        self.setWindowTitle('qqs — Loading rice'); self.setStyleSheet('background:'+theme['background']+';color:'+theme['text_color']+';')
        layout=QVBoxLayout(self); layout.setContentsMargins(theme['padding'],theme['padding'],theme['padding'],theme['padding']); layout.addStretch(3)
        label=LoadingText(theme['message'],theme,max(8,min(90,theme['font_size']))); layout.addWidget(label)
        layout.addSpacing(theme['spacing']); self.bar=SegmentBar(theme); self.bar.setVisible(theme['show_progress']);layout.addWidget(self.bar); layout.addStretch(4)
        footer_theme={**theme,'font':theme['footer_font'],'message_alignment':'center'};footer=LoadingText(theme['footer'],footer_theme,max(8,min(60,theme['footer_font_size'])));footer.setVisible(theme['show_footer']); layout.addWidget(footer)
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor(self.theme['background']))
        if not self.image.isNull():
            scale=max(self.width()/self.image.width(),self.height()/self.image.height())
            width=self.width()/scale;height=self.height()/scale
            painter.setOpacity(self.theme['background_image_opacity']/100)
            painter.drawPixmap(QRectF(self.rect()),self.image,QRectF((self.image.width()-width)/2,(self.image.height()-height)/2,width,height))
    def closeEvent(self,event): event.ignore()

class Window(Customizable,QWidget):
    def __init__(self):
        super().__init__(None,Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle('qqs — Quick Quick Shell'); self.setWindowIcon(QIcon(str(BASE/'assets/logo.png')))
        self.runtime=Runtime(DATA);self.launcher_sessions={}; self.job=None; self.loader=None; self.phase=None; self.log_dialog=None
        self.intentional_stop=False; self.reported_errors=''; self.was_alive=self.runtime.alive(); self.last_log=''; self.dialogs=[]
        self.rices=[]; self.settings={}; self.drag_offset=None
        try:
            self.settings=json.loads((DATA/'preferences.json').read_text()); self.rices=self.settings.get('rices',[])
        except (OSError,ValueError): pass
        self.rices=[infer_legacy_source(r) for r in self.rices]
        self.theme=load_theme('menu'); self.loading_theme=load_theme('loading')
        self.setObjectName('qqs')
        layout=QVBoxLayout(self); layout.setContentsMargins(26,30,26,16); layout.setSpacing(8)
        self.title=QLabel();self.title.setObjectName('title');layout.addWidget(self.title)
        self.input_widget=QWidget();self.input_widget.setObjectName('inputbar');row=QHBoxLayout(self.input_widget);row.setContentsMargins(0,0,0,0);self.input_layout=row;row.setSpacing(9)
        self.source=QLineEdit();self.source.setObjectName('entry'); self.source.setMinimumHeight(40); row.addWidget(self.source,1)
        self.add=QPushButton();self.add.setObjectName('add'); self.add.setMinimumSize(70,40); self.add.clicked.connect(self.add_source); row.addWidget(self.add); layout.addWidget(self.input_widget)
        self.list=QListWidget();self.list.setObjectName('riceList'); self.list.setSpacing(5); self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.itemClicked.connect(lambda item:self.select_rice(item) if self.theme['mouse_single_click'] else None); self.list.itemActivated.connect(self.select_rice)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.list.customContextMenuRequested.connect(self.list_menu)
        layout.addWidget(self.list,1)
        self.empty=QLabel(); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.empty)
        self.footer_widget=QWidget();self.footer_widget.setObjectName('footer');footer=QHBoxLayout(self.footer_widget);footer.setContentsMargins(0,0,0,0); self.status=QLabel();self.status.setObjectName('status'); self.status.setWordWrap(True); footer.addWidget(self.status,1)
        self.logo=Logo(); footer.addWidget(self.logo); layout.addWidget(self.footer_widget)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.customContextMenuRequested.connect(self.menu)
        self.init_customization()
        self.monitor=QTimer(self); self.monitor.timeout.connect(self.poll_runtime); self.monitor.start(150)
        self.reload_appearance(); self.refresh_list()
    def paintEvent(self,event):
        t=self.theme; p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(7,7,self.width()-14,self.height()-14)
        grad=QLinearGradient(r.topLeft(),r.bottomRight()); grad.setColorAt(0,QColor(t['border_secondary_color'])); grad.setColorAt(1,QColor(t['border_color']))
        radius=min(100,t['corner_radius']); wave=min(18,t['wave_depth'])
        left,top,right,bottom=r.left(),r.top(),r.right(),r.bottom()
        path=QPainterPath(); path.moveTo(left+radius,top)
        path.cubicTo(self.width()*.34,top+wave,self.width()*.67,top-wave,right-radius,top+wave)
        path.quadTo(right,top+wave,right,top+radius)
        path.cubicTo(right-wave,self.height()*.35,right+wave/3,self.height()*.68,right,bottom-radius)
        path.quadTo(right,bottom,right-radius,bottom)
        path.cubicTo(self.width()*.66,bottom+wave/3,self.width()*.34,bottom-wave,left+radius,bottom)
        path.quadTo(left,bottom,left,bottom-radius)
        path.cubicTo(left+wave/2,self.height()*.68,left-wave/3,self.height()*.35,left,top+radius)
        path.quadTo(left,top,left+radius,top)
        fill=QLinearGradient(r.topLeft(),r.bottomRight());bg=QColor(t['background']);bg.setAlphaF(bg.alphaF()*min(100,t['background_opacity'])/100);fill.setColorAt(0,bg.lighter(104) if t['background_gradient'] else bg);fill.setColorAt(1,bg)
        p.setPen(QPen(grad,min(16,t['border_width'])) if t['border_width'] else Qt.PenStyle.NoPen); p.setBrush(fill);p.drawPath(path)
        image=getattr(self,'background_pixmap',None)
        if image is not None and not image.isNull():
            scale=max(r.width()/image.width(),r.height()/image.height());sw=r.width()/scale;sh=r.height()/scale
            p.save();p.setClipPath(path);p.setOpacity(min(100,t['background_image_opacity'])/100)
            p.drawPixmap(r,image,QRectF((image.width()-sw)/2,(image.height()-sh)/2,sw,sh));p.restore()
            p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path)
        if t['glass_effect']:
            p.save();p.setClipPath(path)
            highlight=QColor(t['glass_highlight_color']);highlight.setAlphaF(highlight.alphaF()*t['glass_strength']/100*.32)
            clear=QColor(highlight);clear.setAlpha(0)
            sheen=QRadialGradient(QPointF(r.left()+r.width()*.16,r.top()-r.height()*.1),r.width()*.85)
            sheen.setColorAt(0,highlight);sheen.setColorAt(.72,clear)
            p.fillRect(r,sheen)
            edge=QLinearGradient(r.topLeft(),r.bottomRight());rim=QColor(t['glass_highlight_color']);rim.setAlphaF(rim.alphaF()*t['glass_strength']/100*.72)
            fade=QColor(rim);fade.setAlpha(0)
            edge.setColorAt(0,rim);edge.setColorAt(.35,fade);edge.setColorAt(.75,fade);edge.setColorAt(1,rim)
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(edge,1.5));p.drawPath(path)
            p.restore()
    def reload_appearance(self,live=False):
        previous=self.theme;previous_loading=self.loading_theme
        previous_files={key:set(paths) for key,paths in appearance.THEME_FILES.items()}
        previous_style=self.styleSheet();previous_background=getattr(self,'background_pixmap',None)
        selected=self.list.currentItem()
        selected_entry=selected.data(Qt.ItemDataRole.UserRole)['entry'] if selected else None
        try:
            theme=load_theme('menu');loading=load_theme('loading')
            self.theme=theme;self.loading_theme=loading
            self.apply_customization();self.refresh_list()
            if selected_entry:
                for i in range(self.list.count()):
                    item=self.list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole)['entry']==selected_entry and not item.isHidden():self.list.setCurrentItem(item);break
            if self.isVisible():self.position_popup()
        except Exception as e:
            self.theme=previous;self.loading_theme=previous_loading
            appearance.THEME_FILES.clear();appearance.THEME_FILES.update(previous_files)
            try:self.apply_customization();self.refresh_list()
            except Exception:pass
            self.setStyleSheet(previous_style)
            if previous_background is not None:self.background_pixmap=previous_background
            if live:
                DATA.mkdir(parents=True,exist_ok=True)
                with (DATA/'qqs.log').open('a',encoding='utf-8') as log:log.write('Theme reload rejected; previous appearance retained: '+str(e)+'\n')
                self.status.setText('Theme error: '+str(e)+' • Previous appearance retained.');self.watch_themes()
            else:self.failure(str(e))
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'list'):self.update_grid()
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.Type.ActivationChange and self.theme.get('hide_on_focus_loss'):
            def hide_if_inactive():
                active=QApplication.activeWindow()
                if self.isVisible() and not self.isActiveWindow() and not QApplication.activePopupWidget() and not (active and self.isAncestorOf(active)) and not self.phase:self.hide()
            QTimer.singleShot(70,hide_if_inactive)
    def refresh_list(self):
        self.list.clear();rices=list(self.rices)
        if self.theme['list_sort']=='name':rices.sort(key=lambda r:r['name'].casefold())
        elif self.theme['list_sort']=='recent':rices.sort(key=lambda r:r.get('last_used',0),reverse=True)
        alignment={'left':Qt.AlignmentFlag.AlignLeft,'center':Qt.AlignmentFlag.AlignHCenter,'right':Qt.AlignmentFlag.AlignRight}[self.theme['row_alignment']]
        for number,rice in enumerate(rices,1):
            label=(str(number)+'. ' if self.theme['row_show_index'] else '')+rice['name']
            if self.theme['row_show_source']:label+='\n'+rice.get('source',str(rice_folder(rice)))
            item=QListWidgetItem(label);item.setData(Qt.ItemDataRole.UserRole,rice);item.setTextAlignment(alignment|Qt.AlignmentFlag.AlignVCenter)
            if self.theme['show_icons']:item.setIcon(QIcon(rice['icon_file']) if rice.get('icon_file') and Path(rice['icon_file']).is_file() else self.row_icon)
            item.setToolTip(NAMES.get(rice.get('backend','quickshell'),'Custom launcher')+'\n'+rice['entry']);self.list.addItem(item)
            if self.runtime.alive() and rice['entry']==self.runtime.state.get('entry'):self.list.setCurrentItem(item)
        self.update_grid();self.filter_rices()
    def save_list(self):
        # Preserve preferences written by previous versions and login restoration.
        try: values=json.loads((DATA/'preferences.json').read_text())
        except (OSError,ValueError): values={}
        values.update({'rices':self.rices,'keep_alive':True}); write_json(DATA/'preferences.json',values)
    def add_source(self):
        text=self.source.text().strip()
        if not text or self.job and self.job.isRunning(): return
        self.add.setEnabled(False); self.source.setEnabled(False); self.status.setText('Importing rice…')
        self.job=ImportJob(text,DATA); self.job.done.connect(self.imported); self.job.failed.connect(self.failure)
        self.job.finished.connect(self.import_finished); self.job.start()
    def import_finished(self): self.add.setEnabled(True); self.source.setEnabled(True)
    def imported(self,root,name,metadata=None):
        try:
            entries=entry_files(root)
            if len(entries)>1:
                choices=[NAMES[backend_for(p)]+' · '+str(p.relative_to(root)) for p in entries]
                selected,ok=QInputDialog.getItem(self,'Select shell entry','Several shell entry points were found. Choose the one to add:',choices,0,False)
                if not ok: self.status.setText('Rice import cancelled.'); return
                entry=entries[choices.index(selected)]
            else: entry=entries[0]
            entry=str(entry.resolve());backend=backend_for(entry);launch_options={}
            if backend=='eww':
                windows=eww_windows(entry)
                if not windows:raise ValueError('No Eww defwindow found. Select a launch profile for this configuration.')
                default=windows.index('bar') if 'bar' in windows else 0
                window,ok=QInputDialog.getItem(self,'Eww startup window','Choose the window to open when starting this rice:',windows,default,False)
                if not ok:self.status.setText('Rice import cancelled.');return
                launch_options={'windows':[window]}
            if any(r['entry']==entry for r in self.rices):
                self.status.setText('This rice is already in your list.'); return
            new_rice={'name':name,'entry':entry,'root':str(root),'backend':backend,'launch_options':launch_options,**(metadata or {'source_kind':'local','source':str(root)})}
            report=dependency_report(new_rice)
            self.rices.append(new_rice)
            try: self.save_list()
            except Exception: self.rices.pop(); raise
            self.source.clear(); self.refresh_list(); self.status.setText('Added to saved rices: '+name)
            missing=[item for item,binary in report if not binary]
            note='\nReferenced launchers not installed: '+', '.join(missing)+'. See Launcher dependencies in the rice menu.' if missing else ''
            QMessageBox.information(self,'Rice saved',name+' was added to saved rices. Select it to start.'+note)
        except Exception: self.failure(traceback.format_exc())
    def failure(self,details):
        DATA.mkdir(parents=True,exist_ok=True)
        with (DATA/'qqs.log').open('a',encoding='utf-8') as f: f.write(time.strftime('\n[%Y-%m-%d %H:%M:%S] ')+details+'\n')
        self.status.setText('Operation failed. Open logs for details.')
        if self.loader: self.loader.hide(); self.loader.deleteLater(); self.loader=None
        self.phase=None; self.last_log=self.runtime.text(); self.reported_errors='\n'.join(line for line in self.last_log.splitlines() if 'ERROR:' in line); self.show(); self.raise_()
        QMessageBox.warning(self,'qqs — Error',details[-1600:]+'\n\nThe log viewer will open next.')
        self.show_logs()
    def show_logs(self):
        dialog=QDialog(self); dialog.setWindowTitle('qqs — Launcher and shell logs'); dialog.resize(880,560)
        layout=QVBoxLayout(dialog); label=QLabel(str(DATA/'qqs.log')+'\n'+str(DATA/'session.log')); label.setWordWrap(True); layout.addWidget(label)
        text=QPlainTextEdit(); text.setReadOnly(True); text.setFont(QFont('monospace',10)); layout.addWidget(text)
        def read():
            content=[]
            for filename in ('qqs.log','session.log'):
                p=DATA/filename
                if p.exists():
                    with p.open('rb') as f:
                        f.seek(0,2); size=f.tell(); f.seek(max(0,size-100000)); content.append('=== '+filename+' ===\n'+f.read().decode('utf-8',errors='replace'))
            text.setPlainText('\n\n'.join(content) or 'No logs have been recorded.')
        row=QHBoxLayout(); layout.addLayout(row)
        refresh=QPushButton('Refresh logs'); refresh.clicked.connect(read); row.addWidget(refresh)
        for title,filename in [('Open launcher log','qqs.log'),('Open shell log','session.log')]:
            button=QPushButton(title);button.setEnabled((DATA/filename).exists())
            button.clicked.connect(lambda checked=False,filename=filename:QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA/filename))));row.addWidget(button)
        read(); self.log_dialog=dialog; dialog.show()
    def select_rice(self,item):
        if self.phase: return
        rice=item.data(Qt.ItemDataRole.UserRole); entry=rice['entry']
        try:
            if not Path(entry).is_file(): raise FileNotFoundError('Rice entry file is missing: '+entry)
            backend=backend_for(entry)
            plan=launch_plan(entry,rice.get('launch_options',{}),quickshell=quickshell_binary() if backend=='quickshell' else None)
            if not os.environ.get('WAYLAND_DISPLAY'): raise RuntimeError('Open qqs inside your Hyprland / Wayland session.')
            if plan.get('transient'):
                self.run_launcher(plan,entry,rice['name']);return
            plan=prepare_bindings(rice,DATA,plan)
            self.loading_theme=load_theme('loading');display_theme={**self.loading_theme,'message':self.loading_theme['message'].replace('{rice}',rice['name'])}; self.loader=Loading(display_theme)
            screen=self.screen(); self.loader.setGeometry(screen.geometry());
            if self.loading_theme['fullscreen']:self.loader.showFullScreen()
            else:
                size=lambda value,total:round(total*float(value[:-1])/100) if isinstance(value,str) else value
                self.loader.resize(size(self.loading_theme['width'],screen.availableGeometry().width()),size(self.loading_theme['height'],screen.availableGeometry().height()));self.loader.move(screen.availableGeometry().center()-self.loader.rect().center());self.loader.show()
            self.hide()
            self.next_run=(plan,entry);self.next_options=rice.get('launch_options',{}); self.phase='stopping'; self.intentional_stop=True
            self.started=time.monotonic(); self.runtime.stop()
        except Exception: self.failure(traceback.format_exc())
    def poll_runtime(self):
        for key,(runtime,label) in list(self.launcher_sessions.items()):
            code=runtime.poll()
            if not runtime.alive():
                self.launcher_sessions.pop(key,None)
                log=runtime.text()
                if code not in (0,None) or 'QQS_ERROR:' in log:self.failure(label+' could not run.\n'+log[-8000:])
        code=self.runtime.poll(); alive=self.runtime.alive()
        if self.phase=='stopping':
            if not alive:
                try:
                    self.runtime.start_plan(*self.next_run,remember=False); self.reported_errors=''; self.phase='starting'; self.started=time.monotonic(); self.was_alive=True; self.intentional_stop=False
                except Exception: self.failure(traceback.format_exc())
            elif time.monotonic()-self.started>7: self.failure('The previous rice could not be stopped. The new rice was not launched.')
            return
        if self.phase=='starting':
            log=self.runtime.text(); elapsed=(time.monotonic()-self.started)*1000
            if not alive or 'QQS_ERROR:' in log or (self.next_run[0]['backend']=='quickshell' and ('ERROR:' in log or 'Failed to load configuration' in log)):
                self.intentional_stop=True; self.runtime.stop(); self.was_alive=False
                self.failure(startup_failure(code)+'\n'+log[-8000:]); return
            if elapsed>=max(1000,self.loading_theme['startup_timeout_ms']):
                self.intentional_stop=True; self.runtime.stop(); self.failure('Rice startup timed out.\n'+log[-8000:]); return
            if 'QQS_READY' in log and elapsed>=max(600,self.loading_theme['minimum_display_ms']):
                try:
                    write_json(DATA/'last-interface.json',{'entry':self.next_run[1],'launch_options':self.next_options,'backend':self.next_run[0]['backend']})
                    for rice in self.rices:
                        if rice['entry']==self.next_run[1]:rice['last_used']=time.time()
                    self.save_list()
                except Exception: self.failure(traceback.format_exc()); return
                self.loader.hide(); self.loader.deleteLater(); self.loader=None; self.phase=None; self.refresh_list()
            return
        if self.was_alive and not alive:
            self.was_alive=False
            if not self.intentional_stop:
                log=self.runtime.text()
                if code not in (0,None) or 'ERROR:' in log: self.failure(f'Rice exited unexpectedly (exit code {code}).\n'+log[-8000:])
        elif alive:
            self.was_alive=True
            log=self.runtime.text()
            error_lines='\n'.join(line for line in log.splitlines() if 'ERROR:' in line)
            if error_lines and error_lines!=self.reported_errors:
                self.reported_errors=error_lines; self.last_log=log; self.failure('The running rice reported an error.\n'+log[-8000:])
    def stop_rice(self):
        if not self.runtime.alive():self.status.setText('No rice started by qqs is running.');return
        self.intentional_stop=True; self.runtime.stop(); self.status.setText('Stopping the rice started by qqs…')
    def remove_rice(self,rice):
        old=self.rices[:]; self.rices.remove(rice)
        try: self.save_list(); self.refresh_list()
        except Exception: self.rices=old; self.failure(traceback.format_exc())
    def open_location(self,path):
        path=Path(path)
        if not path.exists(): self.failure('Location does not exist: '+str(path)); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
    def open_source(self,rice):
        source=rice.get('source')
        if not source: self.status.setText('The original import source was not saved. Use Edit import source to add it.'); return
        if rice.get('source_kind')=='github':
            url=QUrl(source)
            if url.scheme()!='https' or url.host()!='github.com': self.failure('Invalid saved GitHub source URL.'); return
            QDesktopServices.openUrl(url)
        else: self.open_location(source)
    def set_source(self,rice):
        text,ok=QInputDialog.getText(self,'Edit import source','Original GitHub URL, folder, ZIP archive or shell entry file:',text=rice.get('source',''))
        if not ok or not text.strip(): return
        try:
            metadata=source_metadata(text); previous=dict(rice);rice.update(metadata)
            try:self.save_list()
            except Exception:rice.clear();rice.update(previous);raise
            self.refresh_list()
        except Exception:self.failure(traceback.format_exc())
    def choose_rice_icon(self,rice):
        name,_=QFileDialog.getOpenFileName(self,'Choose rice icon',str(Path.home()),'Images (*.png *.svg *.jpg *.jpeg *.webp)')
        if not name:return
        if QIcon(name).isNull():self.failure('Cannot load rice icon: '+name);return
        previous=rice.get('icon_file');rice['icon_file']=name
        try:
            self.save_list();self.refresh_list()
            self.status.setText('List icon saved.' if self.theme['show_icons'] else 'List icon saved; icons are hidden by the current appearance.')
        except Exception:
            if previous:rice['icon_file']=previous
            else:rice.pop('icon_file',None)
            self.failure(traceback.format_exc())
    def rename_rice(self,rice):
        name,ok=QInputDialog.getText(self,'Rename rice','Name:',text=rice['name'])
        if not ok or not name.strip():return
        previous=rice['name'];rice['name']=name.strip()
        try:self.save_list();self.refresh_list()
        except Exception:rice['name']=previous;self.failure(traceback.format_exc())
    def preview_files(self,rice):
        root=rice_folder(rice).resolve()
        if not root.is_dir():self.failure('Rice folder is missing: '+str(root));return
        dialog=QDialog(self);dialog.setWindowTitle('qqs — Read-only file preview · '+rice['name']);dialog.resize(780,500)
        layout=QVBoxLayout(dialog);info=QLabel('Folder: '+str(root)+'\nSource: '+rice.get('source','Not recorded'))
        info.setWordWrap(True);info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);layout.addWidget(info)
        splitter=QSplitter();layout.addWidget(splitter,1)
        model=QFileSystemModel(dialog);model.setReadOnly(True);model.setRootPath(str(root));model.setFilter(QDir.Filter.AllEntries|QDir.Filter.NoDotAndDotDot)
        tree=QTreeView();tree.setModel(model);tree.setRootIndex(model.index(str(root)));tree.setHeaderHidden(True)
        for column in (1,2,3):tree.hideColumn(column)
        splitter.addWidget(tree);editor=QPlainTextEdit();editor.setReadOnly(True);editor.setFont(QFont('monospace',10));splitter.addWidget(editor);splitter.setSizes([240,540])
        selected=QLabel();selected.setWordWrap(True);layout.addWidget(selected)
        current=[Path(rice['entry'])]
        def read(path):
            path=Path(path)
            if not path.is_file():return
            try:
                if not path.resolve().is_relative_to(root):raise ValueError('Symbolic link points outside this rice folder.')
                if path.stat().st_size>2*1024*1024:raise ValueError('Preview is limited to files up to 2 MB. Use Open selected file for larger files.')
                text=path.read_text(encoding='utf-8')
                if '\x00' in text:raise ValueError('Binary file. Use Open selected file to view it.')
                editor.setPlainText(text);current[0]=path;selected.setText(str(path.relative_to(root)))
            except (OSError,UnicodeError,ValueError) as e:editor.setPlainText(str(e));current[0]=path;selected.setText(str(path))
        tree.clicked.connect(lambda index:read(model.filePath(index)))
        actions=QHBoxLayout();layout.addLayout(actions)
        for text,callback in [('Open selected file',lambda:self.open_location(current[0])),('Open configuration folder',lambda:self.open_location(root)),(source_action(rice),lambda:self.open_source(rice))]:
            button=QPushButton(text);button.clicked.connect(callback);button.setEnabled(bool(rice.get('source')) if text==source_action(rice) else True);actions.addWidget(button)
        read(rice['entry']);self.dialogs.append(dialog);dialog.finished.connect(lambda _:self.dialogs.remove(dialog) if dialog in self.dialogs else None);dialog.show()
        return dialog
    def run_launcher(self,plan,entry,label):
        try:
            key=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()[:16]
            runtime=Runtime(DATA/'launcher-sessions'/key)
            if runtime.alive():self.status.setText('This launcher is already open.');self.hide();return
            runtime.start_plan({**plan,'transient':True},entry,remember=False)
            self.launcher_sessions[key]=(runtime,label);self.hide()
        except Exception:self.failure(traceback.format_exc())
    def open_integrated_launcher(self,item,rice):
        try:self.run_launcher(item_plan(item),item.get('entry',rice['entry']),item['name'])
        except Exception:self.failure(traceback.format_exc())
    def show_launcher_dependencies(self,rice):
        try:
            report=dependency_report(rice)
            message='\n'.join(name+': '+(binary or 'not installed / not on PATH') for name,binary in report) or 'No known external launchers were found in this configuration.'
            message+='\n\nDetected references may be optional. Explicit requirements in qqs-shell.json are checked before switching. Configuration wrappers apply only to processes started by this rice.'
            QMessageBox.information(self,'Launcher dependencies',message)
        except Exception:self.failure(traceback.format_exc())
    def can_trash(self,rice):
        root=rice_folder(rice).resolve();library=(DATA/'interfaces').resolve()
        if not root.is_dir() or root==library or not root.is_relative_to(library):return False
        if self.runtime.alive() and Path(self.runtime.state['entry']).resolve().is_relative_to(root):return False
        for runtime,_ in self.launcher_sessions.values():
            if runtime.alive() and Path(runtime.state['entry']).resolve().is_relative_to(root):return False
        return True
    def trash_rice(self,rice):
        if not self.can_trash(rice):self.status.setText('Stop this rice before moving its imported folder to Trash. External folders can only be removed from saved rices.');return
        root=rice_folder(rice).resolve()
        if QMessageBox.question(self,'Move imported rice to Trash','Move this imported folder and its files to Trash?\n'+str(root)+'\nAll entries pointing into this folder will be removed from the list.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:
            result=QFile.moveToTrash(str(root));success=result[0] if isinstance(result,tuple) else result
            if not success:raise OSError('Could not move rice folder to Trash.')
            self.rices=[r for r in self.rices if not Path(r['entry']).resolve().is_relative_to(root)]
            self.save_list();self.refresh_list();self.status.setText('Imported rice moved to Trash.')
        except Exception:self.failure(traceback.format_exc())
    def rice_actions(self,rice):
        menu=QMenu(self)
        try:
            found=integrations(rice)
            if found:
                submenu=menu.addMenu('Launchers for this rice')
                for item in found:submenu.addAction(item['name'],lambda checked=False,item=item:self.open_integrated_launcher(item,rice))
        except Exception as error:
            action=menu.addAction('Invalid launcher profile: '+str(error));action.setEnabled(False)
        menu.addAction('Launcher dependencies…',lambda:self.show_launcher_dependencies(rice))
        menu.addSeparator()
        menu.addAction('View configuration files…',lambda:self.preview_files(rice))
        menu.addAction('Open configuration folder',lambda:self.open_location(rice_folder(rice)))
        menu.addAction('Open shell entry file',lambda:self.open_location(rice['entry']))
        action=menu.addAction(source_action(rice),lambda:self.open_source(rice));action.setEnabled(bool(rice.get('source')))
        menu.addAction('Edit import source…',lambda:self.set_source(rice))
        menu.addAction('Copy configuration folder path',lambda:QApplication.clipboard().setText(str(rice_folder(rice))))
        menu.addSeparator();menu.addAction('Rename saved rice…',lambda:self.rename_rice(rice));menu.addAction('Choose list icon…',lambda:self.choose_rice_icon(rice))
        menu.addAction('Remove from saved rices',lambda:self.remove_rice(rice))
        action=menu.addAction('Move imported folder to Trash…',lambda:self.trash_rice(rice));action.setEnabled(self.can_trash(rice))
        return menu
    def list_menu(self,pos):
        item=self.list.itemAt(pos)
        if not item:self.menu(self.list.mapTo(self,pos));return
        self.rice_actions(item.data(Qt.ItemDataRole.UserRole)).exec(self.list.mapToGlobal(pos))
    def apply_preset(self,name):
        path=appearance.theme_path('menu')
        try:
            if path.exists():shutil.copy2(path,path.with_suffix(path.suffix+'.bak'))
            if path.suffix=='.lua':appearance.write_theme(path,{'preset':name})
            else:path.write_text('@theme "'+name+'"\n',encoding='utf-8')
            self.reload_appearance()
        except Exception:self.failure(traceback.format_exc())
    def restore_previous_theme(self):
        path=appearance.theme_path('menu');backup=path.with_suffix(path.suffix+'.bak')
        try:
            current=path.read_text();old=backup.read_text();path.write_text(old);backup.write_text(current);self.reload_appearance()
        except Exception:self.failure(traceback.format_exc())
    def change_theme_format(self,selected):
        try:appearance.set_format(selected);self.reload_appearance()
        except Exception:self.failure(traceback.format_exc())
    def import_menu_theme(self):
        name,_=QFileDialog.getOpenFileName(self,'Import menu appearance',str(CONFIG),'qqs themes (*.lua *.rasi)')
        if not name:return
        try:
            source=Path(name);values=appearance.read_values(source,'menu',set())
            values=appearance.validate_theme(values,dict(appearance.MENU),source,'menu')
            path=appearance.theme_path('menu')
            if path.exists():shutil.copy2(path,path.with_suffix(path.suffix+'.bak'))
            appearance.write_theme(path,values);self.reload_appearance()
        except Exception:self.failure(traceback.format_exc())
    def export_menu_theme(self):
        extension=appearance.active_format()
        name,_=QFileDialog.getSaveFileName(self,'Export menu appearance',str(Path.home()/('qqs-menu.'+extension)),'qqs themes (*.lua *.rasi)')
        if not name:return
        try:
            path=Path(name)
            if path.suffix not in ('.lua','.rasi'):path=path.with_suffix('.'+extension)
            appearance.write_theme(path,self.theme)
        except Exception:self.failure(traceback.format_exc())
    def menu(self,pos):
        menu=QMenu(self); menu.addAction('Open appearance folder',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG))))
        menu.addAction('Open menu appearance file',lambda:self.open_location(appearance.theme_path('menu')))
        menu.addAction('Open loading appearance file',lambda:self.open_location(appearance.theme_path('loading')))
        presets=menu.addMenu('Appearance presets')
        for preset in ('qqs-original','qqs-dark','qqs-grid','qqs-minimal','qqs-liquid-glass'):
            presets.addAction({'qqs-original':'Original','qqs-dark':'Dark','qqs-grid':'Grid','qqs-minimal':'Minimal','qqs-liquid-glass':'Liquid Glass'}.get(preset,preset),lambda checked=False,name=preset:self.apply_preset(name))
        restore=presets.addAction('Restore previous appearance',self.restore_previous_theme);restore.setEnabled(appearance.theme_path('menu').with_suffix('.'+appearance.active_format()+'.bak').exists())
        presets.addSeparator();presets.addAction('Import menu theme…',self.import_menu_theme);presets.addAction('Export menu theme…',self.export_menu_theme)
        formats=presets.addMenu('Appearance file format')
        for extension in ('lua','rasi'):
            action=formats.addAction(extension.upper());action.setCheckable(True);action.setChecked(appearance.active_format()==extension)
            action.triggered.connect(lambda checked=False,extension=extension:self.change_theme_format(extension))
        menu.addAction('Customization guide',lambda:self.open_location(BASE/'THEMING.md'))
        menu.addAction('Reload appearance files',self.reload_appearance); menu.addAction('View launcher and shell logs',self.show_logs)
        menu.addAction('Stop running rice',self.stop_rice)
        from startup import configure
        flag=DATA/'login-restore.json'; enabled=False
        try: enabled=json.loads(flag.read_text()).get('enabled',False)
        except (OSError,ValueError): pass
        action=menu.addAction('Start last-used rice at login'); action.setCheckable(True); action.setChecked(enabled)
        def set_restore(value):
            try: configure(value,DATA)
            except Exception: self.failure(traceback.format_exc())
        action.toggled.connect(set_restore)
        menu.addSeparator(); menu.addAction('Exit qqs (keep rice running)',self.quit_app); menu.exec(self.mapToGlobal(pos))
    def toggle(self):
        if self.loader: self.loader.raise_(); return
        if self.isVisible(): self.hide()
        else:
            self.reload_appearance(); self.refresh_list();
            if self.theme['clear_query_on_open']:self.source.clear()
            self.position_popup(); self.show(); self.raise_(); self.activateWindow(); self.source.setFocus()
    def closeEvent(self,event):
        self.hide(); event.ignore()
    def quit_app(self):
        if self.job and self.job.isRunning(): self.status.setText('An import is in progress. Wait for it to finish before exiting.'); return
        if self.phase: self.status.setText('A rice switch is in progress. Wait for it to finish before exiting.'); return
        QApplication.instance().quit()
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton: self.drag_offset=event.globalPosition().toPoint()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self,event):
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton: self.move(event.globalPosition().toPoint()-self.drag_offset)
    def mouseReleaseEvent(self,event): self.drag_offset=None

def main():
    QLocale.setDefault(QLocale(QLocale.Language.English))
    app=QApplication(sys.argv); app.setApplicationName('qqs'); app.setDesktopFileName('qqs'); app.setApplicationDisplayName('qqs — Quick Quick Shell')
    app.setQuitOnLastWindowClosed(False); app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    try: launch_environment(data_dir=DATA)
    except OSError as e:
        QMessageBox.critical(None,'qqs — Data error',str(e)); return 1
    socket_name='qqs-launcher-'+str(os.getuid())+'-'+hashlib.sha256(str(DATA).encode()).hexdigest()[:12]
    peer=QLocalSocket(); peer.connectToServer(socket_name)
    if peer.waitForConnected(400):
        peer.write(b'toggle'); peer.waitForBytesWritten(500); return 0
    server=QLocalServer(); server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption); QLocalServer.removeServer(socket_name)
    if not server.listen(socket_name): return 1
    try: window=Window()
    except Exception:
        DATA.mkdir(parents=True,exist_ok=True)
        details=traceback.format_exc()
        with (DATA/'qqs.log').open('a',encoding='utf-8') as f: f.write(details+'\n')
        QMessageBox.critical(None,'qqs — Configuration error',details+'\nLog: '+str(DATA/'qqs.log'))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA/'qqs.log'))); return 1
    def connected():
        sock=server.nextPendingConnection()
        def toggle():
            sock.readAll(); window.toggle(); sock.disconnectFromServer()
        sock.readyRead.connect(toggle)
        if sock.bytesAvailable(): toggle()
        sock.disconnected.connect(sock.deleteLater)
    server.newConnection.connect(connected)
    window.position_popup();window.show()
    return app.exec()

if __name__=='__main__': sys.exit(main())
