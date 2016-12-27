from gevent import monkey
monkey.patch_all()
import gc
import queue
import datetime
import gevent
import requests
import threading
import pymysql as mariadb
# Threads may share the module, but not connections.
# 线程可以共享模块，但不能共享连接。
# https://www.python.org/dev/peps/pep-0249/#threadsafety
from requests.packages.urllib3 import Retry
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup


def mariadb_insert(connection, user_name, level, referer, type):
    with connection as cursor:
        SQL = '''INSERT INTO relationship (user_name, level, referer, type) VALUES (%s,%s,%s,%s)'''
        cursor.execute(SQL, (user_name, level, referer, type))
    cursor.close()


def mariadb_select_forward(connection, user_name, referer):
    with connection as cursor:
        SQL = '''SELECT * FROM relationship WHERE user_name=%s AND referer=%s'''
        cursor.execute(SQL, (user_name, referer))
    user = cursor.fetchone()
    cursor.close()
    return user

def find_all_level(connection, level):
    with connection as cursor:
        SQL = '''SELECT * FROM relationship WHERE level=%s'''
        cursor.execute(SQL, level)
    levels = cursor.fetchall()
    cursor.close()
    return levels


def check_relationship(connection, username, referer):
    # 校验是否存在本关系
    # 不存在时候插入
    if mariadb_select_forward(
            connection=connection,
            user_name=username,
            referer=referer,
    ) is None:
        return True
    else:
        return False


# followers生产者<->followers消费者
# following生产者<->following消费者
class github_spider(object):
    '''
    爬虫类
    '''

    def __init__(self):
        self.base_url = 'https://github.com/'

    def __get_page(self, url):
        '''
        获得页面html
        :param url:用户对应页面
        :return: 页面soup对象
        '''
        s = requests.Session()
        https_retries = Retry(50)
        https = requests.adapters.HTTPAdapter(max_retries=https_retries)
        s.mount('https://', https)
        r = s.get(url=url, timeout=30)
        res = (r.text.encode(r.encoding).decode('utf8'))
        soup = BeautifulSoup(res, 'html.parser')
        return soup

    def user_info(self, username):
        '''
        用户信息页
        :param username:用户名
        :return: dict[username],dict[email]
        '''
        try:
            node = self.__get_page(url='%s%s' % (self.base_url, username))
            email = node.find('li', {'aria-label': 'Email'}).text.strip()
        except Exception as e:
            email = ''
        return {'username': username, 'email': email}

    def __relationship(self, username, action, page):
        tmp = []
        try:
            # 遍历用户列表
            node = self.__get_page(
                url='%s%s/?page=%s&tab=%s' %
                (self.base_url, username, page, action))
            all_user_node = node.find(
                'div', {'class': 'js-repo-filter position-relative'})
            users_node = all_user_node.find_all(
                'div', {
                    'class': 'd-table col-12 width-full py-4 border-bottom border-gray-light'})
            if users_node == []:
                return tmp
            for i in users_node:
                user = i.find('span', {'class': 'link-gray pl-1'}).text
                tmp.append(user)
        except Exception as e:
            pass
        return tmp

    def user_relationship(self, username, action):
        page = 1
        while True:
            tmp = self.__relationship(
                username=username, action=action, page=page)
            if tmp == []:
                with open('log.txt','a') as f:
                    f.write('%s %s %s %s page break\n' % (str(datetime.datetime.now()), username, action, page))
                f.close()
                break
            with open('log.txt', 'a') as f:
                f.write('%s %s %s %s page running\n' % (str(datetime.datetime.now()), username, action, page))
            f.close()
            if action == 'followers':
                _followers_producer = followers_producer(tmp=tmp)
                _followers_consumer = followers_consumer()
                _followers_producer.start()
                _followers_producer.join()
                _followers_consumer.start()
            elif action == 'following':
                _following_producer = following_producer(tmp=tmp)
                _following_consumer = following_consumer()
                _following_producer.start()
                _following_producer.join()
                _following_consumer.start()
            page += 1


class followers_producer(threading.Thread):
    '''
    followers生产者
    '''

    def __init__(self, tmp):
        threading.Thread.__init__(self)
        threading.Thread.name = 'followers_producer'
        self.tmp = tmp
        self.data = followers_queue

    def run(self):
        followers_lock.acquire()
        for i in self.tmp:
            # print(i)
            self.data.put(i)


class following_producer(threading.Thread):
    '''
    following生产者
    '''

    def __init__(self, tmp):
        threading.Thread.__init__(self)
        threading.Thread.name = 'following_producer'
        self.tmp = tmp
        self.data = following_queue

    def run(self):
        following_lock.acquire()
        for i in self.tmp:
            # print(i)

            self.data.put(i)


class followers_consumer(threading.Thread):
    '''
    followers的消费者
    '''

    def __init__(self):
        threading.Thread.__init__(self)
        threading.Thread.name = 'followers_consumer'
        self.referer = referer

    def run(self):
        followers_lock.release()
        # follower线程连接
        follower_connection = mariadb.connect(
            host='localhost',
            port=3306,
            user='github',
            passwd='test',
            db='github',
            charset='UTF8')
        while True:

            try:
                user_name = followers_queue.get()
                if check_relationship(
                        connection=follower_connection,
                        username=user_name,
                        referer=referer):
                    mariadb_insert(
                        connection=follower_connection,
                        user_name=user_name,
                        level=level + 1,
                        referer=referer,
                        type='follower')
            except Exception as e:
                break
        follower_connection.close()


class following_consumer(threading.Thread):
    '''
    following的消费者
    '''

    def __init__(self):
        threading.Thread.__init__(self)
        threading.Thread.name = 'following_consumer'
        self.referer = referer

    def run(self):
        following_lock.release()
        # following线程连接
        following_connection = mariadb.connect(
            host='localhost',
            port=3306,
            user='github',
            passwd='test',
            db='github',
            charset='UTF8')
        while True:
            try:
                user_name = following_queue.get()

                if check_relationship(
                        connection=following_connection,
                        username=user_name,
                        referer=referer):
                    mariadb_insert(
                        connection=following_connection,
                        user_name=user_name,
                        level=level + 1,
                        referer=referer,
                        type='following')
            except Exception as e:
                break
        following_connection.close()




def followers(username):
    new.user_relationship(username=username, action='followers')


def following(username):
    new.user_relationship(username=username, action='following')


def user_info(username):
    gevent.joinall([
        gevent.spawn(followers, username),
        gevent.spawn(following, username),
    ])
    gevent.get_hub().join()

if __name__ == '__main__':
    new = github_spider()

    # 主线程连接
    conn = mariadb.connect(
        host='localhost',
        port=3306,
        user='github',
        passwd='test',
        db='github',
        charset='UTF8')

    # 目标用户
    username = 'HolaJam'
    # 初始等级
    level = 0
    # 初始referer
    default_referer = username
    # 初始关系类型
    type = 'self'
    # 加入初始用户
    mariadb_insert(
        connection=conn,
        user_name=username,
        level=level,
        referer=default_referer,
        type=type)
    # followers生产者队列
    followers_queue = queue.Queue()
    # following生产者队列
    following_queue = queue.Queue()
    # 对线程上锁
    # followers锁
    followers_lock = threading.Lock()
    # following锁
    following_lock = threading.Lock()
    while level != 6:
        start_time = datetime.datetime.now()
        for i in find_all_level(connection=conn, level=level):
            referer = i[1]
            # i:(1, 'HolaJam', '0', ' ', 'self')
            user_info(username=i[1])
            gc.collect()

        level += 1
        end_time = datetime.datetime.now()
        print('level %s cost %s' % (level, end_time-start_time))

# 消费者 - 生产者 模型基本完成，在INSERT时候不会消耗太多时间
# todo 完善其他功能
# todo 增加抓取的多线程
# todo sqlalchemy解决Too many connections问题
