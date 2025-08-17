"""
ダッシュボード処理の最適化版
"""
from datetime import datetime, timedelta, time
from django.db import models
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Sum, Prefetch
from django.utils import timezone
from django.core.cache import cache
from .models import Plan, Result, WorkCalendar, WorkingDay, Part, PlannedHourlyProduction, PartChangeDowntime, Line, Machine
import jpholiday
from collections import defaultdict
import calendar
import logging
import hashlib

logger = logging.getLogger(__name__)


def get_dashboard_data_optimized(line_id, date_str):
    """最適化されたダッシュボード用データ取得"""
    # キャッシュキーを生成
    cache_key = f"dashboard_data_{line_id}_{date_str}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        logger.info(f"キャッシュからダッシュボードデータを取得: {cache_key}")
        return cached_data
    
    logger.info(f"ダッシュボードデータを新規計算: line_id={line_id}, date={date_str}")
    
    # --- 1. 基本データ取得 ---
    line = get_object_or_404(Line, id=line_id)
    line_name = line.name

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = timezone.now().date()

    # --- 2. 計画データを一括取得 ---
    plans = Plan.objects.filter(
        line_id=line_id, 
        date=date
    ).select_related('part', 'part__category').order_by('sequence')

    # --- 3. 設備情報を一括取得 ---
    count_target_machines = Machine.objects.filter(
        line_id=line_id, 
        is_active=True,
        is_count_target=True
    ).order_by('name')
    count_target_machine_names = [m.name for m in count_target_machines]
    
    # --- 4. 稼働カレンダー取得 ---
    try:
        work_calendar = WorkCalendar.objects.get(line_id=line_id)
        work_start_time = work_calendar.work_start_time
        morning_meeting_duration = work_calendar.morning_meeting_duration
    except WorkCalendar.DoesNotExist:
        work_start_time = time(8, 30)
        morning_meeting_duration = 15
    
    # --- 5. 時間範囲計算 ---
    actual_work_start = datetime.combine(date, work_start_time) + timedelta(minutes=morning_meeting_duration)
    next_day_work_start = actual_work_start + timedelta(days=1)
    start_str = actual_work_start.strftime('%Y%m%d%H%M%S')
    end_str = next_day_work_start.strftime('%Y%m%d%H%M%S')
    
    # --- 6. 実績データを一括取得 ---
    results = Result.objects.filter(
        line=line_name,
        machine__in=count_target_machine_names,
        timestamp__gte=start_str,
        timestamp__lt=end_str,
        judgment='1',
        sta_no1='SAND'
    )
    
    # --- 7. 機種別データ集計（最適化） ---
    part_data = {}
    
    # 計画数量を集計
    for plan in plans:
        pname = plan.part.name
    失敗: {e}")シュ一括クリアに"キャッning(far  logger.w  :
        ption as ecept Exce  ex件")
      s)}(keylenュを一括クリア: {のダッシュボードキャッシne_id}ン{li(f"ライinfoer.     logg        
       )e(*keyslet client.de               
    :   if keys     
        ern)(patteysnt.ks = clie     key          *"
 _{line_id}__data"*dashboardttern = fpa          nt()
      liet_ce._cache.ge cachnt =clie              nt'):
  e, 'get_cliecache._cachttr(nd hasahe') acache, '_cac hasattr(     if  he
     mport cache ire.cacngo.coja    from d
        y:   tr
     シュクリアRedis使用時のキャッ       #  
  re
            import
    make_keyutils importe.cache.corfrom django.  
      ッチング）リア（パターンマキャッシュをクインの全    # 該当ラelse:
    }")
    key: {cache_ドキャッシュをクリアo(f"ダッシュボーgger.inf   lo   key)
  cache_che.delete(    ca  
  ate_str}"line_id}_{drd_data_{oashb"dae_key = fcach
         date_str: if"""
   ドキャッシュをクリア"ダッシュボー:
    ""e_str=None)atne_id, dche(licadashboard_f clear_

dern color
tu   
    re 3600)
 color,(cache_key,   cache.set時間）
  ッシュに保存（1 # キャ"
    
   2x}{b:02x}{g:0x}"#{r:02color = f    ss)
n, lightnee, saturatiogb(hub = hsl_to_r r, g, 
   255)
    5), int(b * , int(g * 2555) * 2eturn int(r        r    
   1/3)
 , h -  q(p,rgb= hue_to_       b )
      hgb(p, q, = hue_to_r    g
         h + 1/3)o_rgb(p, q, hue_t  r =         l - q
 = 2 *    p      
    s - l * s+  else l  l < 0.5+ s) if* (1   q = l            
           n p
 retur               3 - t) * 6
q - p) * (2/ (eturn p +         r        
   /3:   if t < 2       n q
      ur   ret             1/2:
        if t <            
  t- p) * 6 *n p + (q tur re                 
  /6:  if t < 1        1
         t -=         
         1:     if t >         = 1
   t +          
          t < 0:  if            q, t):
   (p,  hue_to_rgb       def
         else:     l
r = g = b =            :
  if s == 0          
0
     / 10      l = l
  00/ 1s = s      h / 360
    h = 
       l):b(h, s, rgdef hsl_to_に変換
     # HSLをRGB 
   0)
   , 16) % 2h[5:7]hashex_= 45 + (int(ss neght 25)
    li3:5], 16) %h[t(hex_has = 65 + (insaturation
    , 16) % 360hex_hash[:3] int(e =huを生成
      # HSL色空間で色
  t()
    gesxdish_object.heha_hash =  hex)
   de()coenh_input.d5(hasashlib.mbject = hhash_o    ''}"
 art_name orart_id}_{pt = f"{p  hash_inpuッシュを生成
  を組み合わせてハ種IDと名前  
    # 機r
  ched_colo  return ca      r:
ed_colof cach  
    iey)
  _ket(cacheache.glor = cched_co
    ca'}"e or 'rt_nam_id}_{pa_color_{partartf"pache_key = "
    c""成（キャッシュ付き）れた機種色生適化さ""最e):
    "name=Non_id, part_timized(partolor_operate_part_c
def gen
計算エラー'
 return '      e}")
 終了予測計算エラー: {rror(f"logger.e      n as e:
  ept Exceptio   exc     
    
    計算不可'  return '         else:
     ']
    sage_result['mes forecast      return:
      ssage')ult.get('mest_resrecafo  elif M')
      rftime('%H:%n_time'].stetiot['complast_resulreturn forec        ):
    time'etion_t.get('complt_resuld forecasaness') lt.get('succecast_resu for        if
        
_id, date)recast(lineetion_foate_complulce.calcservit_lt = forecassurecast_re  fo    e()
  ationServiccastCalculore = Fcerecast_servi       forvice
 lculationSerecastCaimport Foce _servi.forecastrvicesom .se        fr try:
""
   終了予測時刻計算"""最適化されたe):
    "d, datized(line_ioptimt_time_ate_forecascalcul0


def    return    : {e}")
  数計算エラー投入.error(f"      loggeron as e:
  tixcept Excep
    e
        untn input_co retur       
t_count}")"投入数: {inpunfo(fer.ilogg       
    t()
     ).coun     ND'
   a_no1='SA        sttr,
    nd_s__lt=e timestamp         
  _str,te=startp__gam     timest     s,
  e_name_in=machin machine_     ,
      ine_name=line           l
 cts.filter(Result.objet = nput_coun        i try:
   数計算"""
投入"最適化された
    ""nd_str):art_str, e, stachine_namesline_name, mmized(pti_oinput_counte_lculat
def cay_data

turn hourl
    re ecord)
   _rappend(hourourly_data.  h
        
      l_qtytual'] += acl_actuard['totaco    hour_re        
    lanned_qtyd'] += pl_planne['totaur_record         ho 
                      }
                tual_qty,
 acual':'act                   
 y,anned_qtpl': annedpl           '     ,
    'color']d][_it_info[partcolor': par    '                ]['name'],
art_id_info[pname': part       '            = {
 art_id] 'parts'][prd[ur_reco        ho 
                     
  , 0)_id.get(partindex]actual[hour_rly_ = houactual_qty              _id, 0)
  (part_index].getplanned[houry_y = hourl planned_qt           :
    rt_infoid in pa part_        if   _ids:
 ll_partart_id in a   for p   
     )
     s()_index].keyourrly_actual[h| set(hou()) ].keys_indexhour_planned[= set(hourlyids l_part_
        al合種を統   # 全ての機 
              }
    {}
  arts':    'p       : 0,
  actual''total_       : 0,
     nned'lal_p'tota           ay_time,
 displour':      'h{
       _record =        hour 
       
 H:%M')}~)"e('%rt.strftimstative_me}({effecsplay_tif"{dilay_time =      disp
       ng_duration)rning_meeties=moinut timedelta(mstart +our_start = hective_     eff
       ex == 0: hour_ind   if    '%H:%M')
 ftime(_start.stre = hourtimplay_     disの計算
    # 表示時間    
          
 index)(hours=hour_elta+ timedtart_time) date, work_sme.combine(tistart = dater_    hou):
    nge(24_index in ra hour   for
    
 data = []    hourly_構築 ---
データを時間別  # --- 3. e
    
   continu          xist:
     art.DoesNotE  except P             }
           
      rt_name)part_id, paimized(or_optate_part_colercolor': gen      '       
           t_name,e': par       'nam             {
     id] =t_info[part_   par           
      _info:rt not in paif part_id            みの機種用）
    に追加（実績の part_info          #      
       
         ecord_count_id] += rx][partl[hour_indehourly_actua           
     _obj.idid = part  part_             e)
 =part_nam.get(nametsbjecbj = Part.o     part_o          
 ry:       t      IDを取得
   # Part          
    ]
       rd_count'result['reco = record_count      ]
      lt['part'sue = re    part_nam
        s:ulthour_ressult in  for re         
  
          )')
  _numbererialt('s_count=Counrd reco      tate(
     art').anno ).values('p      _end_str
 __lt=result   timestamp
         start_str,result_amp__gte=timest           s.filter(
 ltults = resures     hour_取得
    この時間帯の実績を      # 
      M%S')
   %d%H%('%Y%mmetit_end.strf= resulr t_end_stesul r
       H%M%S')e('%Y%m%d%ftimstart.strr = result_t_start_stul  res       
 =1)
      a(hoursdeltmert + tir_staou = hult_end res          
   tart
  ur_s= hoesult_start           r else:
  on)
       tirag_durning_meetina(minutes=modeltmer_start + tiart = houstresult_           = 0:
  =our_index       if h間を考慮
 帯は朝礼時最初の時間  #        
       r_index)
a(hours=hou) + timedeltmerk_start_tiate, woombine(dtime.ct = datehour_star:
        range(24)ndex in  hour_i
    forで取得一括 各時間帯の実績を    
    #dict(int))
default(lambda: ltdict= defau_actual ly hour--
    -一括集計データを時間別に-- 2. 実績 # - 
             }
 )
me part_naid,art__optimized(ppart_color': generate_or     'col      e,
 t_nam'name': par    
        t_id] = {art_info[par      pqty
  nned_+= plapart_id] our][planned[hhourly_         
   tity']
    ned_quan= php['plannned_qty      plae']
   'part__namame = php[     part_n']
   rt_idpa = php['rt_idpa
        p['hour']our = ph:
        hta_darlyhou planned_in for php 
    
   fo = {}art_in
    pdict(int))faulta: deict(lambdaultded = deflannhourly_p
    別計画データを辞書に整理
    # 時間
     )
   d_quantity', 'plannet__name'id', 'parr', 'part_ 'hou(
       values).lated('part'_reselectdate
    ).e=
        datne_id,id=li      line_r(
  cts.filteuction.objerlyProdounnedH = Plaataed_hourly_d plann取得 ---
   を一括画時間別データ- 1. 計  
    # --""
  時間別データ生成""""最適化された):
    urationeeting_drning_m mot_time,work_star                            ts, 
     esulchines, rive_mactplans, ae_id, date, timized(linta_op_hourly_dadef generate_data


oarddashbeturn 
    
    r)y}" {cache_keタをキャッシュに保存:ドデー"ダッシュボーo(f.inf   logger00)
 , 3_datadashboard, che_keyet(ca.s  cache
  ャッシュに保存（5分間） 
    # キ}
   ),
    mat(.isofor().now': timezoneatedupdlast_   '
     ime,orecast_tme': frecast_ti    'fong,
    ng': remainiaini   'remate,
     ent_rchievemte': at_ra 'achievemen       count,
nt': input_input_cou
        'al_actual,ual': total_acttot   ',
     otal_planned': tannedpl'total_      
  data,y_ourly': h  'hourl)),
      es(t_data.valus': list(par  'part      d_data = {
oardashb---
    12. 結果データ   # --- ate)

   dne_id,(litimizede_opt_timcasorelate_fcu= calt_time  forecas---
   測時刻計算  --- 11. 終了予   #
 
    )
 end_str, start_str,ne_namesachi_target_muntconame,    line_  mized(
   opti_count_te_inputnt = calcula   input_cou最適化） ---
  投入数計算（ 10.    # ---al)

_actu - totaltal_planned, toing = max(0
    remain0lanned else  if total_pd * 100)total_plannectual / al_arate = (totvement_   achielues())
 part_data.van for d id['actual']  sum(ctual =tal_a))
    toues(valta.t_dad in par'] for ['plannednned = sum(d   total_pla 総計算 ---
 --- 9.

    # ion
    )rating_duning_meettime, mor_start_ork   wts, 
     nes, result_machiunt_targens, co date, pla_id,ne        liimized(
data_optate_hourly_ata = gener hourly_d） ---
   成（最適化. 時間別データ生 --- 8   #
 * 100)
anned ty / pl= (actual_qt_rate'] men]['achieve[pnameta    part_da               
 ned > 0:if plan             ]
   nned'ame]['pla_data[pnrt= pa  planned               l_qty
 actual'] ='actua][a[pnamet_dat     par       ]
    t'ual_counult['actesual_qty = r      act         rt_data:
 name in pa    if p      ']
  art= result['p   pname         :
 alsactut in part_resulor    f 
       )
       
      al_number')erit=Count('sounl_cua     act(
       atet').annot'parlues(       ).vart_names
 part__in=pa         er(
   filt= results.rt_actuals      paans]
   n in plfor plame rt.nan.paplart_names = [pa       ans:
 
    if pl# 実績数量を一括集計
    ity
anned_quant= plan.plnned'] +plaata[pname]['art_d    p  }
    
          ),an.part.namepart.id, plimized(plan._color_opte_part': generat  'color        
      0,e': ratachievement_  '            l': 0,
  tua    'ac           ed': 0,
   'plann            : pname,
  me'  'na             name] = {
 art_data[p    p
        _data: in partnot  if pname   