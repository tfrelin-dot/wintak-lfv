#!/usr/bin/env python3
"""Generate a cautious, non-operational WinTAK KML overlay from LFV WFS."""
import datetime as dt
import html
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE='https://daim.lfv.se/geoserver/wfs?service=WFS&version=1.1.0&request=GetFeature&outputFormat=application/json&srsName=EPSG:4326&typeName='
OUT=Path('site'); OUT.mkdir(exist_ok=True)
NS='http://www.opengis.net/kml/2.2'
ET.register_namespace('',NS)
def node(parent, tag, text=None, **attrib):
    e=ET.SubElement(parent,'{%s}%s'%(NS,tag),attrib)
    if text is not None:e.text=str(text)
    return e

def fetch(layer):
    req=urllib.request.Request(BASE+layer,headers={'User-Agent':'WinTAK-LFV-Experimental/0.1'})
    with urllib.request.urlopen(req,timeout=45) as r:
        data=json.load(r)
    if data.get('type')!='FeatureCollection' or not isinstance(data.get('features'),list):
        raise ValueError('Invalid WFS GeoJSON for '+layer)
    return data['features']

def coord_string(ring):
    return ' '.join(f'{pt[0]},{pt[1]},0' for pt in ring)

def add_geom(parent, geom):
    if not geom:return False
    typ=geom.get('type'); c=geom.get('coordinates')
    polys=[c] if typ=='Polygon' else c if typ=='MultiPolygon' else []
    if not polys:return False
    holder=node(parent,'MultiGeometry') if len(polys)>1 else parent
    for rings in polys:
        if not rings:continue
        poly=node(holder,'Polygon'); node(poly,'tessellate','1')
        for i,ring in enumerate(rings):
            if len(ring)<4:continue
            bound=node(poly,'outerBoundaryIs' if i==0 else 'innerBoundaryIs')
            lr=node(bound,'LinearRing'); node(lr,'coordinates',coord_string(ring))
    return True

def add_style(doc,id,color):
    style=node(doc,'Style',id=id)
    ls=node(style,'LineStyle');node(ls,'color',color);node(ls,'width','2')
    ps=node(style,'PolyStyle');node(ps,'color',color)

def make_pm(folder,name,description,geom,style,extra):
    pm=node(folder,'Placemark');node(pm,'name',name);node(pm,'styleUrl','#'+style)
    node(pm,'description',description)
    ext=node(pm,'ExtendedData')
    for k,v in extra.items():
        d=node(ext,'Data',name=k);node(d,'value',v or '')
    if not add_geom(pm,geom):folder.remove(pm);return False
    return True

def dms(s):
    # e.g. 631034N 0145615E (NOTAM ITEM_E). Strict 7/8-digit DMS only.
    lat,lon=s.split()
    def conv(v,deg):
        a=int(v[:deg]);b=int(v[deg:deg+2]);c=int(v[deg+2:deg+4]);hem=v[-1]
        if b>59 or c>59 or (deg==2 and a>90) or (deg==3 and a>180):raise ValueError()
        x=a+b/60+c/3600
        return -x if hem in 'SW' else x
    return [conv(lon,3),conv(lat,2)]

def exact_notam_polygon(text):
    # Only use explicit coordinates from 'AREA BOUNDED BY:'; otherwise omit geometry.
    m=re.search(r'AREA BOUNDED BY\s*:\s*(.*?)(?:\.\s|\nFLIGHT|\nAREA|\nVERTICAL|\nLOWER|$)',text,re.I|re.S)
    if not m:return None
    pairs=re.findall(r'\b\d{6}N\s+\d{7}E\b',m.group(1))
    if len(pairs)<4:return None
    try:ring=[dms(p) for p in pairs]
    except ValueError:return None
    if ring[0]!=ring[-1]:ring.append(ring[0])
    if len(ring)<4:return None
    return {'type':'Polygon','coordinates':[ring]}

def main():
    now=dt.datetime.now(dt.timezone.utc)
    # Fail closed: never silently publish stale data if any source fails.
    rsta=fetch('mais:RSTA')
    notams=fetch('dynais:NOTAM')
    root=ET.Element('{%s}kml'%NS); doc=node(root,'Document')
    node(doc,'name','LFV WinTAK - EXPERIMENTELL, ej för flygoperativ användning')
    node(doc,'description','Ej verifierad realtidsstatus. Lila = okänd aktiveringsstatus. Kontrollera alltid officiell AIS/ATS.')
    # KML ABGR: purple line+very transparent fill, one style for now
    add_style(doc,'unknown','55ff00aa')
    a=node(doc,'Folder');node(a,'name','R-områden – status OKÄND')
    n_r=0
    for f in rsta:
        p=f.get('properties') or {}
        name=str(p.get('NAMEOFAREA') or p.get('LOCATION') or f.get('id') or 'R-område')
        info={'Källa':'LFV WFS mais:RSTA','Status':'OKÄND - DUP ej integrerad','Hämtad UTC':now.isoformat(),'Undre gräns':str(p.get('LOWER','')),'Övre gräns':str(p.get('UPPER',''))}
        desc='\n'.join(f'{k}: {v}' for k,v in info.items())
        n_r+=make_pm(a,name,desc,f.get('geometry'),'unknown',info)
    b=node(doc,'Folder');node(b,'name','Tillfälliga NOTAM R-områden – status OKÄND')
    n_n=0; skipped=0
    for f in notams:
        p=f.get('properties') or {}; body=str(p.get('ITEM_E') or '')
        if not re.search(r'TEMPORARY RESTRICTED AREA\s+ES\s?R\s?\d+',body,re.I):continue
        # NOTAM GeoJSON often shows an approximate circle: use only explicit ITEM_E boundary.
        geom=exact_notam_polygon(body)
        if not geom:skipped+=1;continue
        match=re.search(r'\bES\s?R\s?\d+\b',body,re.I)
        ident=match.group(0).replace(' ','') if match else str(f.get('id'))
        code=f"{p.get('SERIES','')}{p.get('NO','')}/{str(p.get('YEAR','')).zfill(2)}"
        info={'NOTAM':code,'Giltig från UTC':str(p.get('STARTVALIDITY') or ''),'Giltig till UTC':str(p.get('ENDVALIDITY') or ''),'Tidsschema D':str(p.get('ITEM_D') or 'Ej angivet'),'Undre gräns':str(p.get('ITEM_F') or ''),'Övre gräns':str(p.get('ITEM_G') or ''),'Status':'OKÄND - giltighet är inte verifierad aktivering','Källa':'LFV WFS dynais:NOTAM','Hämtad UTC':now.isoformat(),'NOTAM-text':body}
        desc='\n\n'.join(f'{k}: {v}' for k,v in info.items())
        n_n+=make_pm(b,ident+' '+code,desc,geom,'unknown',info)
    ET.ElementTree(root).write(OUT/'lfv.kml',encoding='utf-8',xml_declaration=True)
    (OUT/'status.json').write_text(json.dumps({'generated_utc':now.isoformat(),'r_areas':n_r,'temporary_notam_areas':n_n,'notam_missing_exact_geometry':skipped,'status':'unknown','warning':'NOT FOR OPERATIONAL FLIGHT USE'},indent=2),encoding='utf-8')
    print(f'Generated {n_r} R polygons, {n_n} exact NOTAM polygons; omitted {skipped} NOTAMs without validated exact boundary')

if __name__=='__main__':main()
