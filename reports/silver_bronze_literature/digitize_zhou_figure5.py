import csv, math
import numpy as np
from scipy.ndimage import label,find_objects
from PIL import Image
from pathlib import Path
img=np.array(Image.open('/tmp/zhou_page14.png').convert('RGB'))
colors={'Silver':(6,156,207),'Bronze':(165,190,106)}
panels=[(189,423,184,482,5),(497,731,184,482,5),(805,1039,184,482,5),(1113,1348,184,482,5),(189,423,597,892,5),(497,731,597,892,5),(805,1039,597,892,5),(1113,1348,597,892,6)]
rows=[]
for algorithm,color in colors.items():
 lab,_=label(np.all(img==color,axis=2));boxes=[]
 for sl in find_objects(lab):
  if sl is None:continue
  y,x=sl
  if y.stop-y.start>=4 and x.stop-x.start>=2:boxes.append((x.start,x.stop,y.start,y.stop))
 for group,(left,right,top,bottom,decades) in enumerate(panels):
  selected=sorted([b for b in boxes if left<b[0]<right and top<b[2]<bottom and abs(b[3]-(bottom-1))<=2]);assert len(selected)==8,(algorithm,group,selected)
  for j,(x0,x1,y0,y1) in enumerate(selected):
   val=10**((bottom-(y0-1))*decades/(bottom-top)); low=10**((bottom-(y0+1))*decades/(bottom-top)); high=10**((bottom-(y0-3))*decades/(bottom-top))
   rows.append(dict(algorithm=algorithm,instance=group*8+j+1,chart_estimate=round(val,3),chart_lower_pixel_2=round(low,3),chart_upper_pixel_2=round(high,3),bar_top_pixel_y=y0,chart_log_decades=decades,raw_time_if_divided_by_29_5=round(val*29.5,2) if algorithm=='Silver' else '',raw_lower_if_divided_by_29_5=round(low*29.5,2) if algorithm=='Silver' else '',raw_upper_if_divided_by_29_5=round(high*29.5,2) if algorithm=='Silver' else ''))
rows.sort(key=lambda x:(x['instance'],x['algorithm']))
p=Path('reports/silver_bronze_literature/zhou2024_figure5_digitized_estimates.csv')
with p.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print('rows',len(rows))
for r in rows[:6]:print(r)
