# github_relationship

## 目的
**获得以目标用户为起点的，六度人脉理论**

## 实现
### 一般
使用Python完成数据的抓取，存入**适当的数据库**中，可以很简单的获得用户与用户之间的关系，用于与repo的关系。  
具体分为Neo4j，MariaDB，MongoDB的版本，如果发现了不错的数据库会增加对应的版本。

## 约定
#### 关系的完善
用户的关注是个人行为，因此互相关注并非一条关系（指程序中的```each```）。将互相关注的这种关系拆分为4份，A关注B，B关注A，A是B的粉丝，B是A的粉丝。


##版本
### 使用Neo4j的版本
已经实现用户与用户之间的关系，但测试发现：
```json
level0 0:00:03.252803
level1 0:01:12.411496
level2 1:23.26.322980
level3 在9小时内未遍历完成
```
在push时候，数据库中有40k的节点数量，协程已经不能满足效率了。
~~后续会补充star，repo等节点，或者现在就做？~~


#### *为什么放弃*
很简单在做完```关系的完善```部分后，效率尿崩，而且可能是因为节点和关系的数量不断增加，即便不更改关系效率依然很慢。如图~  
![](http://p1.bqimg.com/567571/57dada0593f34ad0.png)


### 使用MariaDB的版本
已经实现用户与用户之间的关系，目前正在稳定的运行。
测试发现，以我为起点的用户基数如下：
```json
SELECT COUNT(*) FROM relationship WHERE level=0; //零度人脉（目标用户自己）
1
SELECT COUNT(*) FROM relationship WHERE level=1; //一度人脉
39
SELECT COUNT(*) FROM relationship WHERE level=2; //二度人脉
616
SELECT COUNT(*) FROM relationship WHERE level=3; //三度人脉
25280
这里讨论的人脉数目并非是用户节点或者用户总数，而是在某度人脉中的关系的总量。如果刻意需要查询用户数目，可以使用如下的操作：
SELECT DISTINCT COUNT(user_name) FROM relationship WHERE level=1; //查询零度人脉（目标用户自己）中的用户总数
1
SELECT COUNT(T.A) FROM (SELECT DISTINCT(user_name) AS A FROM relationship WHERE user_name!='HolaJam' AND level=1) T  //查询一度人脉中的用户总数
24
```

### 使用MongoDB的版本
#### todo

## 期望
使用Flask展现数据，使用echarts描述数据。

