Tôi đã đọc kỹ paper **“Decomposition-Based Multiobjective Evolutionary Optimization With Tabu Search for Dynamic Pickup and Delivery Problems”**. Thuật toán được đề xuất có tên **MOEA/D-TS**, kết hợp:

* **MOEA/D** để duy trì nhiều hướng tìm kiếm theo các đánh đổi khác nhau giữa độ trễ và quãng đường.
* **Crossover theo tuyến xe** để tăng đa dạng quần thể.
* **Tabu Search** với bốn phép tìm kiếm cục bộ để cải thiện sâu từng nghiệm.
* **Solution transfer** để kế thừa kế hoạch từ khoảng thời gian trước thay vì giải lại hoàn toàn từ đầu. 

---

# 1. Ý tưởng cốt lõi

Bài toán gốc được đánh giá bằng một hàm mục tiêu tổng hợp:

[
TC(x)=\alpha f_1(x)+f_2(x),
]

trong đó:

[
f_1(x)=\text{tổng thời gian giao hàng trễ},
]

[
f_2(x)=\text{quãng đường di chuyển trung bình của các xe}.
]

Mặc dù kết quả cuối cùng vẫn được chọn bằng (TC), tác giả **không trực tiếp tối ưu duy nhất (TC) trong toàn bộ quá trình tìm kiếm**. Thay vào đó, họ tách nó thành hai mục tiêu:

[
\min \left(f_1(x), f_2(x)\right).
]

Lý do là khi chỉ tối ưu (TC), quần thể có thể nhanh chóng tập trung quanh một vùng và mắc kẹt tại cực trị địa phương. Khi giữ riêng (f_1) và (f_2), các nghiệm có nhiều kiểu đánh đổi hơn:

* Giao ngay để giảm trễ nhưng phải đi nhiều.
* Gom các đơn có địa chỉ giống nhau để giảm quãng đường nhưng có thể tăng trễ.

MOEA/D phân bố quần thể theo nhiều mức đánh đổi giữa hai mục tiêu, giúp duy trì đa dạng.

---

# 2. Biểu diễn một nghiệm

Một nghiệm (x) là kế hoạch tuyến của toàn bộ (K) xe:

[
x={r_1,r_2,\ldots,r_K},
]

trong đó (r_k) là chuỗi các điểm pickup và delivery mà xe (k) sẽ phục vụ.

Nghiệm phải thỏa mãn các ràng buộc:

* Tải trọng xe không vượt quá sức chứa.
* Pickup phải diễn ra trước delivery.
* Tuân thủ LIFO.
* Số xe đồng thời sử dụng dock không vượt quá số dock của nhà máy.
* Mỗi đơn hàng phải được gán cho một xe.
* Thời gian hoàn thành cam kết là ràng buộc mềm: giao trễ vẫn được phép nhưng bị phạt trong (f_1).

Trong quá trình khởi tạo, crossover và local search, các nghiệm vi phạm ràng buộc bị loại bỏ hoặc được sửa chữa.

---

# 3. Multiobjectivization và MOEA/D

## 3.1. Các subproblem

MOEA/D tạo ra (N) vector trọng số:

[
\lambda^1,\lambda^2,\ldots,\lambda^N,
]

với:

[
\lambda^i=(\lambda^i_1,\lambda^i_2),\qquad
\lambda^i_1+\lambda^i_2=1.
]

Mỗi vector trọng số tương ứng với một subproblem:

* Một subproblem chú trọng giảm tardiness.
* Một subproblem cân bằng hai mục tiêu.
* Một subproblem chú trọng giảm quãng đường.
* Các subproblem còn lại nằm giữa các hướng trên.

Trong thực nghiệm trên Huawei, paper sử dụng:

[
N=6,\qquad T=2,
]

trong đó (T) là số vector trọng số gần nhất trong neighborhood.

Mỗi cá thể (x^i) trong quần thể tương ứng với subproblem có vector trọng số (\lambda^i).

---

## 3.2. Hàm Tchebycheff

Mỗi subproblem đánh giá nghiệm bằng hàm tổng hợp Tchebycheff:

[
g(x\mid \lambda,z)
==================

\max_{j\in{1,2}}
\lambda_j |f_j(x)-z_j|,
]

với:

[
z=(z_1,z_2)
]

là reference point, trong đó:

[
z_j=\min_{x\in \text{population}} f_j(x).
]

Ý nghĩa của (g):

* (z) là điểm lý tưởng hiện tại.
* (g) đo khoảng cách có trọng số từ nghiệm đến điểm lý tưởng.
* Mỗi vector (\lambda) tạo ra một hướng tối ưu hóa khác nhau.

Paper viết bài toán Tchebycheff dưới dạng phép tối thiểu hóa của biểu thức trên; khi so sánh hai cá thể, thuật toán thực tế dùng giá trị (\max_j\lambda_j|f_j-z_j|).

---

# 4. Toàn bộ thuật toán MOEA/D-TS

DPDP được giải theo rolling horizon. Trong benchmark Huawei, một ngày được chia thành các khoảng dài 10 phút. Tại mỗi khoảng (t), thuật toán chạy một lần để cập nhật kế hoạch.

Luồng tổng thể là:

```text
Tại mỗi time interval t:

1. Nhận trạng thái hiện tại của xe và các đơn hàng mới.
2. Khôi phục nghiệm tốt nhất của interval t-1.
3. Tạo quần thể ban đầu bằng Cheapest Insertion.
4. Khởi tạo các subproblem MOEA/D và reference point.
5. Lặp:
      a. Chọn cha mẹ.
      b. Crossover theo route.
      c. Repair và chèn các đơn chưa được gán.
      d. Cải thiện offspring bằng Tabu Search.
      e. Cập nhật reference point.
      f. Dùng offspring cập nhật các subproblem lân cận.
6. Chọn nghiệm có TC nhỏ nhất trong quần thể.
7. Lưu nghiệm để dùng ở interval tiếp theo.
8. Xuất nghiệm cho simulator thực thi.
```

Ở phần tiếp theo, tôi phân tích từng bước.

---

# 5. Khởi tạo tại mỗi khoảng thời gian

## 5.1. Khôi phục nghiệm cũ

Thuật toán lấy nghiệm tốt nhất của khoảng trước:

[
x_{\text{restore}}.
]

Nghiệm này chứa:

* Các tuyến đang được thực hiện.
* Những pickup hoặc delivery đã cam kết.
* Vị trí và trạng thái hiện tại của xe.
* Những đơn cũ chưa hoàn thành.

Điểm quan trọng là thuật toán **không xây dựng toàn bộ kế hoạch từ đầu**.

Việc kế thừa nghiệm trước giúp:

* Giảm chi phí tính toán.
* Duy trì tính liên tục giữa các interval.
* Bảo toàn các quyết định đã hoặc đang được thực hiện.
* Dành phần lớn thời gian cho việc tối ưu các đơn mới.

Ablation của paper cho thấy việc bỏ solution transfer làm hiệu năng giảm mạnh, đặc biệt ở bài toán lớn, vì khởi tạo lại mỗi interval tiêu tốn quá nhiều thời gian.

---

## 5.2. Tạo (N) chuỗi đơn hàng mới

Giả sử tập đơn hàng mới ở interval hiện tại là:

[
O_t^{new}.
]

Thuật toán tạo (N) hoán vị ngẫu nhiên khác nhau của tập đơn này:

[
\pi^1,\pi^2,\ldots,\pi^N.
]

Mỗi hoán vị xác định thứ tự các đơn được chèn vào nghiệm cũ.

---

## 5.3. Cheapest Insertion

Với mỗi hoán vị (\pi^i), thuật toán lần lượt dùng **Cheapest Insertion — CI** để chèn các đơn mới vào (x_{\text{restore}}).

Về nguyên tắc, đối với một đơn (o), thuật toán xét các khả năng:

* Gán đơn vào xe nào.
* Chèn pickup ở vị trí nào.
* Chèn delivery ở vị trí nào sau pickup.
* Việc chèn có còn thỏa capacity, LIFO, dock và các ràng buộc khác hay không.
* Mức tăng chi phí hoặc giá trị scalarized objective sau khi chèn.

Vị trí hợp lệ có mức tăng nhỏ nhất được chọn.

Do các chuỗi đơn ngẫu nhiên khác nhau, CI tạo ra (N) nghiệm khác nhau:

[
X={x^1,x^2,\ldots,x^N}.
]

Nghiệm vi phạm ràng buộc bị loại ngay trong giai đoạn khởi tạo.

---

## 5.4. Khởi tạo reference point

Sau khi có quần thể:

[
z_1=\min_i f_1(x^i),\qquad
z_2=\min_i f_2(x^i).
]

Reference point này được cập nhật liên tục khi thuật toán tìm được offspring tốt hơn ở một trong hai mục tiêu.

---

# 6. Chọn cha mẹ trong MOEA/D

Với subproblem (i), MOEA/D xác định neighborhood:

[
B(i)={i_1,i_2,\ldots,i_T},
]

gồm (T) vector trọng số gần (\lambda^i) nhất theo khoảng cách Euclidean.

Mating pool (P) được chọn như sau:

[
P=
\begin{cases}
B(i), & \text{với xác suất }\delta,\
{1,\ldots,N}, & \text{ngược lại}.
\end{cases}
]

Sau đó chọn ngẫu nhiên hai cá thể:

[
p_1,p_2\in P.
]

Hai chế độ có vai trò khác nhau:

* Chọn từ neighborhood: khai thác các nghiệm có hướng đánh đổi tương tự.
* Chọn từ toàn quần thể: kết hợp các nghiệm khác biệt, tăng exploration.

Algorithm 2 của paper chỉ viết “chọn hai parent từ (P)” mà không lặp lại cách tạo (P); định nghĩa này được kế thừa từ MOEA/D trong Algorithm 1.

---

# 7. Crossover theo route

Đây là thành phần exploration chính của thuật toán.

Giả sử hai cha mẹ:

[
p_1={r_1^{(1)},\ldots,r_K^{(1)}},
]

[
p_2={r_1^{(2)},\ldots,r_K^{(2)}}.
]

## 7.1. Kế thừa từng route

Khởi tạo:

[
x_{\text{child}}=\varnothing.
]

Với mỗi xe (k=1,\ldots,K), thuật toán chọn ngẫu nhiên:

[
r_k^{child}
===========

\begin{cases}
r_k^{(1)},\
r_k^{(2)}.
\end{cases}
]

Như vậy, offspring có thể lấy:

* Route xe 1 từ cha mẹ 1.
* Route xe 2 từ cha mẹ 2.
* Route xe 3 từ cha mẹ 2.
* Route xe 4 từ cha mẹ 1.

Crossover hoạt động ở mức **route**, không phải cắt và nối trực tiếp chuỗi node như crossover GA thông thường.

Ưu điểm là các cấu trúc route tốt, đã thỏa phần lớn ràng buộc, có khả năng được giữ nguyên.

---

## 7.2. Xóa node trùng lặp

Do cùng một order có thể xuất hiện trong các route lấy từ cả hai cha mẹ, offspring có thể chứa pickup hoặc delivery trùng.

Sau mỗi lần sao chép route, thuật toán xóa các node trùng lặp để mỗi order chỉ được phục vụ một lần.

---

## 7.3. Xác định các order bị thiếu

Sau khi ghép đủ (K) route, một số order có thể:

* Không xuất hiện trong offspring.
* Bị mất trong quá trình xóa duplicate.
* Chỉ có route chứa nó ở phần không được chọn từ hai cha mẹ.

Tất cả order chưa được gán được đưa vào tập:

[
U.
]

---

## 7.4. Chèn lại order bị thiếu

Với mỗi (o_i\in U), thuật toán chèn order vào vị trí hợp lệ làm nhỏ nhất hàm Tchebycheff:

[
g(x_{\text{child}}\mid\lambda,z).
]

Sau bước này, offspring trở thành một nghiệm hoàn chỉnh.

Pseudo-code:

```text
Crossover(p1, p2, K):

    child = empty

    for k = 1,...,K:
        chọn ngẫu nhiên route k từ p1 hoặc p2
        đưa route đó vào child
        xóa các node/order bị trùng

    U = tập order chưa được gán

    for mỗi order o trong U:
        tìm vị trí chèn hợp lệ tốt nhất
        chèn o vào child

    return child
```

Paper đưa ra độ phức tạp mức khái quát:

[
O(K+|U|).
]

Tuy nhiên, đây là cách đếm ở mức số route và số đơn; chi phí thực tế để tìm tất cả vị trí chèn hợp lệ có thể lớn hơn, tùy cách triển khai CI và kiểm tra ràng buộc.

Một điểm chưa được paper đặc tả hoàn toàn là Algorithm 3 chỉ nhận (p_1,p_2,K), nhưng việc chèn theo Eq. (12) về logic còn cần (\lambda) và (z) của subproblem hiện tại. Chúng có thể được sử dụng như trạng thái toàn cục hoặc bị lược khỏi pseudo-code.

---

# 8. Tabu Search

Sau crossover, thuật toán không đưa offspring vào quần thể ngay. Nó chạy Tabu Search để khai thác vùng lân cận của offspring.

Khởi tạo:

[
x_{\text{best}}=x_{\text{current}}=x_{\text{child}}.
]

Tabu Search chạy tối đa `MaxIter` vòng.

---

## 8.1. Bốn local search operator

Tại mỗi lần sinh neighbor, một trong bốn operator được chọn ngẫu nhiên.

### Couple-exchange

Hoán đổi hai cặp pickup–delivery:

[
[x^+,x^-]
\quad\leftrightarrow\quad
[w^+,w^-].
]

Trong đó:

* (x^+): pickup của order (x).
* (x^-): delivery của order (x).

Operator có thể thay đổi cách hai order được phân bố hoặc sắp xếp trong các route.

---

### Block-exchange

Hoán đổi hai block:

[
B_x\quad\leftrightarrow\quad B_w.
]

Block là một đoạn route chứa cấu trúc pickup–delivery được giữ như một đơn vị. Hình 5 của paper minh họa block như một đoạn liên tục được di chuyển mà vẫn giữ thứ tự nội bộ.

Paper không định nghĩa hình thức đầy đủ của block trong bài này mà trỏ tới tài liệu [62] để xem chi tiết.

---

### Couple-relocate

Lấy một cặp pickup–delivery:

[
[z^+,z^-]
]

ra khỏi vị trí hiện tại và chèn vào một vị trí hợp lệ khác, có thể trong cùng route hoặc route khác.

---

### Block-relocate

Lấy toàn bộ block (B_x) và chuyển đến một vị trí hợp lệ mới.

So với couple-relocate, phép này có thể dịch chuyển đồng thời nhiều node có quan hệ cấu trúc với nhau.

---

# 9. Cách Tabu Search chọn bước đi

Với mỗi vòng ngoài của Tabu Search, thuật toán sinh `NeighborThreshold` candidate neighbor.

```text
bestNeighbor = current

lặp NeighborThreshold lần:
    chọn ngẫu nhiên một trong bốn local search
    tmp = áp dụng local search lên current

    nếu tmp không tabu
       và TC(tmp) < TC(bestNeighbor):
           bestNeighbor = tmp
```

Điểm đáng chú ý là **bên trong Tabu Search, các neighbor được đánh giá bằng mục tiêu tổng hợp (TC)**:

[
TC(x)=\alpha f_1(x)+f_2(x),
]

không phải trực tiếp bằng hàm Tchebycheff của subproblem.

Sau khi lấy neighbor tốt nhất:

[
\text{nếu }TC(x_{\text{bestNeighbor}})
<
TC(x_{\text{best}})
]

thì:

[
x_{\text{best}} \leftarrow x_{\text{bestNeighbor}}.
]

Dù neighbor không tốt hơn nghiệm tốt nhất toàn cục của lần Tabu Search, nó vẫn trở thành current solution:

[
x_{\text{current}}\leftarrow x_{\text{bestNeighbor}}.
]

Sau đó tabu list được cập nhật.

Việc cho phép current solution đi đến một nghiệm không cải thiện global best giúp thuật toán vượt qua cực trị địa phương.

---

## 9.1. Pseudo-code Tabu Search

```text
TabuSearch(child):

    best = child
    current = child

    for iter = 1,...,MaxIter:

        bestNeighbor = current

        for nIter = 1,...,NeighborThreshold:

            chọn ngẫu nhiên một trong:
                couple-exchange
                block-exchange
                couple-relocate
                block-relocate

            tmp = local_search(current)

            if tmp không nằm trong tabu list
               và TC(tmp) < TC(bestNeighbor):
                   bestNeighbor = tmp

        if TC(bestNeighbor) < TC(best):
            best = bestNeighbor

        current = bestNeighbor
        cập nhật tabu list

    return best
```

Độ phức tạp mà paper công bố:

[
O(\text{MaxIter}\times\text{NeighborThreshold}).
]

Tương tự crossover, đây là số lần sinh neighbor; chi phí đánh giá và kiểm tra feasibility của mỗi neighbor không được khai triển trong biểu thức này.

---

# 10. Tabu list lưu gì?

Phần mô tả tổng quan của paper nói tabu list lưu các nghiệm đã gặp:

* Một nghiệm khớp với phần tử trong tabu list được xem là tabu.
* Khi danh sách đầy, phần tử cũ nhất bị loại.
* Mục tiêu là ngăn chu kỳ và tránh quay lại những nghiệm vừa thăm.

Tuy nhiên, Algorithm 4 chỉ viết chung:

```text
Update the tabu list
```

Paper không đặc tả rõ trong phần thuật toán:

* Nghiệm được mã hóa như thế nào.
* Tabu list lưu toàn bộ nghiệm hay move attribute.
* Độ dài tabu tenure.
* Có aspiration criterion hay không.
* Cách so sánh hai nghiệm để xác định trùng lặp.

Vì vậy, dựa đúng vào paper, có thể kết luận rằng đây là **solution-based tabu list** ở mức mô tả, nhưng chi tiết triển khai nằm ngoài pseudo-code được công bố.

Đây là điểm quan trọng nếu anh muốn tái hiện thuật toán: không nên tự giả định paper sử dụng hash toàn bộ solution hay tabu move, vì bài không nói rõ.

---

# 11. Cập nhật reference point

Sau khi Tabu Search trả về offspring cải thiện (x_{\text{child}}), cập nhật:

[
z_j\leftarrow
\min\left(z_j,f_j(x_{\text{child}})\right),
\qquad j\in{1,2}.
]

Tức là:

[
z_1=\min(z_1,f_1(x_{\text{child}})),
]

[
z_2=\min(z_2,f_2(x_{\text{child}})).
]

Reference point vì vậy biểu diễn giá trị tốt nhất từng mục tiêu mà thuật toán đã tìm được.

---

# 12. Cập nhật quần thể MOEA/D

Offspring có thể cập nhật nhiều subproblem trong mating pool (P).

Khởi tạo số lần thay thế:

[
c=0.
]

Lần lượt chọn một subproblem (j\in P). Nếu:

[
g(x_{\text{child}}\mid\lambda^j,z)
<
g(x^j\mid\lambda^j,z),
]

thì:

[
x^j\leftarrow x_{\text{child}},
]

và:

[
c\leftarrow c+1.
]

Quá trình dừng khi:

[
c=n_r
]

hoặc (P) rỗng.

Như vậy, một offspring tốt có thể thay thế tối đa (n_r) nghiệm, nhưng chỉ khi offspring tốt hơn theo hướng trọng số của từng subproblem.

Đây chính là cơ chế hợp tác giữa các subproblem:

* Một nghiệm sinh ra cho subproblem (i).
* Nhưng nếu phù hợp với các hướng lân cận, nó có thể cải thiện các subproblem đó.
* Thông tin tốt được lan truyền trong quần thể.

---

# 13. Chọn nghiệm cuối cùng

Sau khi đạt điều kiện dừng, thuật toán không trả toàn bộ Pareto set cho simulator.

Nó chọn:

[
x^*=\arg\min_{x\in X} TC(x),
]

với:

[
TC(x)=\alpha f_1(x)+f_2(x).
]

Nghiệm (x^*):

1. Được xuất ra cho simulator.
2. Được dùng để thực hiện các pickup và delivery trong interval hiện tại.
3. Được lưu vào archive.
4. Trở thành (x_{\text{restore}}) ở interval tiếp theo.

Như vậy:

> **Multiobjective optimization được dùng để tìm kiếm đa dạng, nhưng single weighted objective (TC) được dùng để ra quyết định cuối cùng.**

Đây là điểm quan trọng nhất để hiểu đúng paper. Thuật toán không thay đổi mục tiêu vận hành thực tế của benchmark; multiobjectivization chỉ thay đổi cơ chế tìm kiếm.

---

# 14. Pseudo-code tổng hợp lại

```text
MOEA/D-TS cho mỗi time interval t

Input:
    trạng thái hiện tại của đội xe
    các order cũ chưa hoàn thành
    các order mới O_new
    N vector trọng số
    neighborhood size T

1. Tạo neighborhood B(i) cho từng vector trọng số λ_i.

2. Khôi phục nghiệm tốt nhất của interval trước:
       x_restore

3. Tạo quần thể X:
       for i = 1,...,N:
           tạo một hoán vị ngẫu nhiên của O_new
           x_i = CheapestInsertion(x_restore, permutation_i)
           loại/sửa các phương án không feasible

4. Khởi tạo reference point:
       z_1 = min_i f_1(x_i)
       z_2 = min_i f_2(x_i)

5. while chưa đạt max iteration và chưa hết thời gian:

       for mỗi subproblem i = 1,...,N:

           Với xác suất δ:
               P = B(i)
           ngược lại:
               P = toàn bộ population

           chọn p1, p2 từ P

           child = RouteBasedCrossover(p1, p2)

           xóa duplicate
           chèn các order chưa được gán

           child = TabuSearch(child)

           cập nhật z bằng child

           for j trong P:
               if g(child | λ_j, z) < g(x_j | λ_j, z):
                   x_j = child
               dừng khi đã thay thế tối đa nr nghiệm

6. Chọn:
       x* = argmin TC(x), x thuộc X

7. Archive x*.

8. Xuất x* cho simulator.
```

---

# 15. Vai trò của từng thành phần

| Thành phần               | Chức năng chính                                                    |
| ------------------------ | ------------------------------------------------------------------ |
| Multiobjectivization     | Tách (TC) thành tardiness và distance để duy trì nhiều kiểu nghiệm |
| MOEA/D                   | Phân bố quần thể theo nhiều hướng đánh đổi                         |
| Neighborhood cooperation | Cho phép các subproblem gần nhau chia sẻ nghiệm tốt                |
| Solution transfer        | Kế thừa route từ interval trước, giảm thời gian khởi tạo           |
| Randomized CI            | Tạo nhiều nghiệm ban đầu khác nhau từ cùng một trạng thái          |
| Route-based crossover    | Kết hợp các route tốt và tăng exploration                          |
| Repair/insertion         | Loại duplicate và bảo đảm mọi order được phục vụ                   |
| Tabu Search              | Khai thác sâu quanh offspring                                      |
| Bốn local search         | Thay đổi cặp hoặc block ở cả mức exchange và relocate              |
| Final selection by (TC)  | Chọn đúng nghiệm theo tiêu chí thực tế của benchmark               |

---

# 16. Cân bằng exploration và exploitation

Có thể nhìn MOEA/D-TS thành ba tầng:

## Tầng 1: Khai thác thông tin động

[
x_{\text{restore}}
\rightarrow
\text{Randomized Cheapest Insertion}.
]

Thuật toán kế thừa trạng thái quá khứ và chỉ xử lý phần thay đổi.

## Tầng 2: Exploration

[
\text{MOEA/D decomposition}
+
\text{route-based crossover}.
]

Nhiều hướng mục tiêu và việc trộn route từ hai cha mẹ giúp khám phá các vùng khác nhau.

## Tầng 3: Exploitation

[
\text{Tabu Search}
+
\text{four local operators}.
]

Mỗi offspring tiềm năng được tối ưu sâu trước khi cập nhật quần thể.

Toàn bộ logic là:

[
\boxed{
\text{Transfer}
\rightarrow
\text{Diversify}
\rightarrow
\text{Recombine}
\rightarrow
\text{Intensify}
\rightarrow
\text{Update}
}
]

---

# 17. Những chi tiết paper chưa đặc tả đủ

Để tái lập chính xác thuật toán, bản paper chính còn thiếu một số chi tiết triển khai:

1. Cấu trúc và độ dài cụ thể của tabu list.
2. Tabu list lưu solution, move hay thuộc tính của move.
3. Cách mã hóa và so sánh hai solution trong tabu list.
4. Aspiration criterion có được sử dụng hay không.
5. Giá trị cụ thể của (\delta) và (n_r) trong phần thí nghiệm chính.
6. `MaxIter` và `NeighborThreshold` của Tabu Search.
7. Số candidate thực tế được sinh bởi mỗi local search.
8. Cách định nghĩa chính xác một “block”.
9. Cách repair khi việc chèn order không có vị trí feasible.
10. Crossover chèn order theo vector (\lambda) nào, vì Algorithm 3 không truyền (\lambda,z) vào hàm.
11. Cách xử lý các phần route đã committed và không được phép thay đổi.
12. Chi phí đánh giá dock scheduling được cập nhật toàn phần hay gia tăng.

Do đó, paper mô tả đầy đủ **kiến trúc thuật toán**, nhưng chưa đủ để tái hiện hoàn toàn từng chi tiết chỉ từ pseudo-code trong bài chính. Một triển khai chính xác cần thêm supplementary material hoặc source code của tác giả.
