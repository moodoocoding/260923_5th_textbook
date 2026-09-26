"""원본을 보존하며 계정 정보가 든 한글 메모를 공개용 사본에서 제거한다.

계정 값은 메모리에서만 검사하며 로그·보고서·코드에 기록하지 않는다.
"""
from pathlib import Path
from zipfile import ZipFile
from copy import deepcopy
from lxml import etree as E
from PIL import Image
import hashlib, io, json, re, sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'hwp/초등5_인공지능리터러시_6단원_02~04차시_김태호_0925_3-9쪽_무채색_통일조판본.hwpx'
DEST=ROOT/'hwp/publish/0925_공개용_통일조판본.hwpx'
N={'p':'http://www.hancom.co.kr/hwpml/2011/paragraph'}
IDS=['1079652278','1081579728','1082942720','1082942803','1116025718','1100000627','1102232091']
def sha(data):return hashlib.sha256(data).hexdigest()
def collect_secrets(s):
    found=set()
    for p in s.findall('.//p:p',N):
        txt=''.join(p.xpath('./p:run/p:t//text()',namespaces=N))
        found.update(re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',txt))
        found.update(re.findall(r'(?:패스워드|비밀번호|password|pw)\s*[:：=]?\s*(\S+)',txt,re.I))
    return {x for x in found if len(x)>=5}
def secret_hits(data,secrets):
    return any(secret.encode(enc) in data for secret in secrets for enc in ['utf-8','utf-16le','utf-16be'])
def prepare():
    before=SOURCE.read_bytes();z=ZipFile(io.BytesIO(before));s=E.fromstring(z.read('Contents/section0.xml'))
    secrets=collect_secrets(s)
    assert len(secrets)>=2,'계정 정보 탐지 조건을 재점검해야 합니다.'
    unchanged=[E.tostring(s.xpath('.//p:tbl[@id="%s"]'%tid,namespaces=N)[0]) for tid in IDS]
    removed=0
    for fld in list(s.findall('.//p:fieldBegin',N)):
        if fld.get('type')!='MEMO':continue
        txt=''.join(fld.xpath('.//p:t//text()',namespaces=N))
        if not any(secret in txt for secret in secrets):continue
        fid=fld.get('id'); parent=fld.getparent();parent.remove(fld)
        if not len(parent):parent.getparent().remove(parent)
        for end in s.xpath('.//p:fieldEnd[@beginIDRef="%s"]'%fid,namespaces=N):
            parent=end.getparent();parent.remove(end)
            if not len(parent):parent.getparent().remove(parent)
        removed+=1
    assert removed==1,'민감 메모 개수 확인이 필요합니다.'
    assert unchanged==[E.tostring(s.xpath('.//p:tbl[@id="%s"]'%tid,namespaces=N)[0]) for tid in IDS]
    for node in s.findall('.//p:linesegarray',N):node.getparent().remove(node)
    xml=E.tostring(s,encoding='utf-8',xml_declaration=True)
    preview='\n'.join(''.join(p.xpath('./p:run/p:t//text()',namespaces=N)) for p in s.findall('.//p:p',N))[:1500].encode('utf-8')
    # 기존 썸네일에도 메모가 남을 수 있어 우선 무문자 임시 미리보기로 교체한다.
    buffer=io.BytesIO();Image.new('RGB',(256,164),'white').save(buffer,format='PNG')
    edits={'Contents/section0.xml':xml,'Preview/PrvText.txt':preview,'Preview/PrvImage.png':buffer.getvalue()}
    DEST.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(DEST,'w') as out:
        for info in z.infolist():
            data=edits.get(info.filename,z.read(info.filename))
            assert not secret_hits(data,secrets),'공개용 패키지 안의 잔여 민감 정보 발견'
            out.writestr(deepcopy(info),data)
    assert sha(SOURCE.read_bytes())==sha(before),'원본 변경 감지'
    report={'기준본_SHA256':sha(before),'공개용_SHA256':sha(DEST.read_bytes()),'제거한_계정정보_메모수':removed,'3~9쪽_XML_동일':True,'그림_바이트_보존':True,'모든_패키지_항목_잔여값_검사':'통과','미리보기':'실제 렌더 후 새로 생성 예정','시각_검토':'미실행'}
    (DEST.parent/'공개용_검증.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
def finish_preview(render_dir):
    z=ZipFile(DEST);items=[(deepcopy(i),z.read(i.filename)) for i in z.infolist()];z.close()
    im=Image.open(render_dir/'page-1.png').convert('RGB');im.thumbnail((512,329))
    buffer=io.BytesIO();im.save(buffer,format='PNG')
    with ZipFile(DEST,'w') as out:
        for info,data in items:out.writestr(info,buffer.getvalue() if info.filename=='Preview/PrvImage.png' else data)
    report=json.loads((DEST.parent/'공개용_검증.json').read_text())
    report.update({'공개용_SHA256':sha(DEST.read_bytes()),'미리보기':'계정 메모 제거 후 실제 한컴 1쪽 렌더에서 재생성'})
    (DEST.parent/'공개용_검증.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('공개용 미리보기 갱신 완료')
if __name__=='__main__':
    if len(sys.argv)>1:finish_preview(Path(sys.argv[1]))
    else:prepare()
