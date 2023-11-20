import json
import configparser
import random
import time
from requests import session
from lxml import etree

class LRY:
    def __init__(self):
        self._path = 'config.ini'
        self.config = configparser.ConfigParser()  # 实例化解析对象
        self.config.read(self._path, encoding='utf-8')  # 读文件
        self.REQ = session()
        self.isLogin = False
        self.header = {
            "Cookie": '',
            'Origin': 'https://sso.scnu.edu.cn/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        }
        self.course_chapters = []
        self.course_list = []
        self.题库 = []
        self.init_answer()

    # 随机课程时间
    def randomTime(self):
        # 以下参数非必要勿改
        video_start_time = int(self.config.get("Config",'start_time'))  # 视频时长随机范围（分钟）建议4~7分钟
        video_end_time = int(self.config.get("Config",'end_time'))
        return random.randint(60 * video_start_time, 60 * video_end_time)

    # 文本格式归一化，方便搜题
    def format(self, str):
        formatStr = str.replace("(", '').replace(")", '').replace("（", '').\
                        replace("）", '').replace(" ", '').replace(".", '').\
                      replace("_", '').replace("-", '').replace(",", '').\
                     replace("。", '').replace('\t', '').replace('n', '').replace('\"','').\
                    replace("\xa0","").replace(" ","").replace("\\",'')
        return formatStr

    # 初始化题库
    def init_answer(self):
        with open('题库.txt', 'r', encoding='utf-8') as f:
            self.题库 = [self.format(text).strip('\n') for text in f.readlines()]
            print(self.题库)
            print('[题库初始化成功]\n')
            f.close()
    def updateConfig(self):
        with open(self._path, 'w', encoding='utf-8') as fp:
            self.config.write(fp)

    def login(self,isUpdate):
        """
        :param isUpdate: 是否重新从综合服务登录 （False：使用配置文件存储的 moodlesession登录励儒云）
        """
        moodlesession = self.config.get('Cookie', 'moodlesession')
        if moodlesession == '' or isUpdate:
            header = {
                'Origin': 'https://sso.scnu.edu.cn/',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Referer': 'https://sso.scnu.edu.cn/AccountService/user/login.html'
            }
            print('[综合平台登录]')
            data = {
                'account': self.config.get('Login', 'account'),
                'password': self.config.get('Login', 'password'),
                'rancode': ''
            }
            print(data)
            url = 'https://sso.scnu.edu.cn/AccountService/user/login.html'
            # 初始化登录界面
            self.REQ.get(url, headers=header)
            # 登录
            self.REQ.post(url, headers=header, data=data, allow_redirects=True)
            # 初始化用户信息
            info = 'https://sso.scnu.edu.cn/AccountService/user/info.html'
            res = self.REQ.post(info, headers=header).json()
            print(res)
            if res['msgcode']==-1:
                print('账号密码错误！！')
                return
            self.config.set('Login', 'name', res['name'])
            self.config.set('Login', 'dept', res['dept'])
            self.config.set('Login', 'phone', res['phone'])
            # 生成MoodleSession
            course = self.REQ.get('https://sso.scnu.edu.cn/AccountService/openapi/onekeyapp.html?app_id=61', headers=header,
                             allow_redirects=False)
            moodlesession = self.REQ.get(course.headers['Location'], headers=header, allow_redirects=False).cookies.get(
                'MoodleSession')
            self.config.set('Cookie', 'MoodleSession', moodlesession)
            # 更新MoodleSession
            self.updateConfig()
        else:
            print('[MoodleSession登录]')
        print('姓名:{}'.format(self.config.get('Login', 'name')))
        print('学号:{}'.format(self.config.get('Login', 'account')))
        print('学院:{}'.format(self.config.get('Login', 'dept')))
        print('\n')
        self.header['Cookie'] = 'MoodleSession={};'.format(moodlesession)
        self.isLogin = True

    def getCourseList(self):
        # 跳转到云课堂
        url = 'https://moodle.scnu.edu.cn/'
        res = self.REQ.get(url, headers=self.header)
        element = etree.HTML(res.content)
        #是否登录
        usertext = element.xpath('//span[@class="usertext mr-1"]')
        if usertext==[]:
            # MoodleSessionn失效，重新在综合服务平台登录
            self.login(True)
            url = 'https://moodle.scnu.edu.cn/'
            res = self.REQ.get(url, headers=self.header)
            element = etree.HTML(res.content)

        # 获取课程列表
        nodes = element.xpath(
            '//ul[@class="nav"]/ul[@class="nav"]//li[@class="dropdown"]//ul[@class="dropdown-menu"]//a')
        course_list = []
        href = 'https://moodle.scnu.edu.cn/report/h5pstats/user.php?course='
        for i in nodes:
            course_list.append({"name":i.get('title'),"url": href + i.get('href').split('=')[1]})

        self.course_list = course_list
        self.config.set('Course', 'course_list',str(self.course_list))
        self.updateConfig()
        return self.course_list

    def getCourseChapter(self, course):
        text = self.REQ.get(course["url"], headers=self.header).text
        html = etree.HTML(text)
        a = html.xpath('//div[@class="logininfo"]//a')
        sesskey = a[1].get('href').split('=')[1]
        video_list = []
        _video = etree.HTML(etree.tostring(html.xpath('//tbody')[0]))

        status = html.xpath('//div[@class="no-overflow mt-5"][1]//td')
        index = 0
        for item in html.xpath('//div[@class="no-overflow mt-5"][1]//td//a'):
            state = []
            for j in range(8):
                state.append(status[index].text)
                index=index+1
            state[1] = [item.text, item.get('href').split('=')[1]]
            video_list.append(state)
        question_list = []
        status = html.xpath('//div[@class="no-overflow mt-5"][3]//td')
        index = 0
        for item in html.xpath('//div[@class="no-overflow mt-5"][3]//td//a'):
            state = []
            for j in range(5):
                state.append(status[index].text)
                index = index + 1
            state[1] = [item.text, item.get('href').split('=')[1]]
            question_list.append(state)
        for item in self.course_chapters:
            if item["name"] == course["name"]:
                self.course_chapters.remove(item)
        self.course_chapters.append({"name":course["name"],"url":course["url"],"sesskey":sesskey, "video_list":video_list, "question_list":question_list})
        return {"name":course["name"],"url":course["url"],"sesskey":sesskey, "video_list":video_list, "question_list":question_list}



    def study(self,sesskey,video_item):
        '''
        获取视频在线资源地址（用于获取视频真实时长，！！！以第一次上传视频时长为准，视频总时长不会被后面修改！！！）
        page = self.REQ.get(url=video_url,headers=self.header)
        html = etree.HTML(page.text).xpath("//iframe")[0]
        iframe_src = html.get('src')
        video_html = self.REQ.get(url=iframe_src,headers=self.header)
        video_data_url = video_html.text.split('[{\\\"path\\\":\\\"')[1].split('\\",\\\"mime\\\":')[0].replace("\\",'')
        '''
        data = [{"index": 0, "methodname": "report_h5pstats_set_time",
                 "args": {"time": 30, "finish": 1, "cmid": "0", "total": 300, "progress": "100"}}]
        data[0]['args']['cmid'] = str(video_item[1][1])

        chapter_name = video_item[1][0]
        chapter_time = video_item[2]
        chapter_rtime = video_item[3]
        chapter_progress = video_item[4]
        chapter_isflish = True if video_item[5]=="是的" else False

        self.REQ.get('https://moodle.scnu.edu.cn/mod/h5pactivity/view.php?id={}'.format(video_item[1][1]),headers=self.header)

        total = int(chapter_time.replace("分钟", '').split('.')[0]) * 60 + int(
            chapter_time.replace("分钟", '').split('.')[1]) \
            if chapter_time.__contains__('分钟') else self.randomTime()
        read_time = int(chapter_rtime.replace("分钟", '').split('.')[0]) * 60 + int(
            chapter_rtime.replace("分钟", '').split('.')[1]) \
            if chapter_rtime.__contains__('分钟') else 0
        data[0]['args']['total'] = int(total)
        print('[{}]章节总时长：{}s ,观看时长：{}s ,学习进度：{} ,是否完成：{}.'.format(chapter_name,total,read_time,chapter_progress,chapter_isflish))

        # 视频接口请求
        while read_time<total:
            res = self.REQ.post('https://moodle.scnu.edu.cn/lib/ajax/service.php?sesskey={}'.format(sesskey), data=json.dumps(data), headers=self.header)
            read_time+=30
            print('[{}]章节总时长：{}s ,观看时长：{}s ,学习进度：{} ,是否完成：{}.'.format(chapter_name, total, read_time,
                                                                                     '{}%'.format(int((read_time/total)*100)), read_time>=total))
            if read_time<total:
                time.sleep(30)
    def auto_answer(self,sesskey,cmid):
        url = 'https://moodle.scnu.edu.cn/mod/quiz/startattempt.php'
        data = {'cmid': cmid,
                'sesskey': sesskey,
                '_qf__mod_quiz_preflight_check_form': 1,
                'submitbutton': '开始答题'}
        # 获取题目
        res = self.REQ.post(url,data=data,headers=self.header,allow_redirects=False)
        if not res.headers.__contains__("Location"):
            print('该章节测试次数已达上限！')
            return
        location = res.headers['Location']
        attempt = location.split('=')[1].split('&')[0]
        questions = []
        page = 0
        while True:
            end = False
            question = self.REQ.get(url="{}&page={}".format(location,page), headers=self.header)
            page = page+1

            question_list = etree.HTML(question.text).xpath('.//div[@class="formulation clearfix"]')
            for item in question_list:
                id = item.xpath('.//input[@type="hidden"]')[0].get('name').replace(':sequencecheck', '')
                answer = []
                ans = item.xpath('.//div[@class="flex-fill ml-1"]')
                for i in ans:
                    if i.text != None:
                        answer.append(self.format(i.text))
                    else:
                        answer.append(self.format(i.xpath('normalize-space(.//p[@dir="ltr"][1])')))
                title = item.xpath('normalize-space(.//div[@class="qtext"])')
                # title = item.xpath('.//div[@class="qtext"]')[0].text
                # if title == None:
                #    title = item.xpath('normalize-space(.//div[@class="qtext"]//p[@dir="ltr"][1])')
                for q in questions:
                    if id == q['id']:
                        end=True
                if not end:
                    questions.append({'id': id, 'question': self.format(title), 'answer': answer})
            if end:
                break

        data = {
            'attempt': int(attempt),
            'thispage': 0,
            'nextpage': -1,
            'timeup': 0,
            'sesskey': sesskey,
            'scrollpos':'',
                'slots': ''
        }
        for i in questions:
            data['slots'] = data['slots']+i['id'].split(':')[1].replace('_','')+','
            data['{}:flagged'.format(i['id'])]=0
            data['{}:sequencecheck'.format(i['id'])]=1
            ans_index = self.getAnswer(i)
            data['{}answer'.format(i['id'])] = ans_index
            print(i)
            print("答案:[{}]".format(i['answer'][ans_index] if ans_index!=-1 else "未找到答案！"))
        data["slots"]=data['slots'].strip(",")

        save_url = 'https://moodle.scnu.edu.cn/mod/quiz/autosave.ajax.php'
        save = self.REQ.post(save_url,data=data,headers=self.header)
        print(save.json())


    def getAnswer(self,question):
        ans_index = -1
        for item in self.题库:
            if item.__contains__(question['question']) or question['question'].__contains__(item):
                index = self.题库.index(item)
                # 标题附近寻找 （题库有点乱，不整理了就这样了）
                for ans in question['answer']:
                    for add in range(10):
                        if self.题库[index + add].__contains__(ans):
                            ans_index = question['answer'].index(ans)
        return ans_index

if __name__ == '__main__':
    lry = LRY()
    # 是否重新从综合服务登录 （False：使用配置文件存储的 moodlesession登录励儒云）
    lry.login(False)
    if lry.isLogin:
        course_list = lry.getCourseList()
        print("课程列表:")
        for course in course_list:
            print("{}.{}".format(course_list.index(course) + 1, course['name']))

        while True:
            print('--------------------------------------')
            try:
                index = eval(input("请输入所需学习课程序号:\n"))
                if index > -1 and index < len(course_list):
                    index = index-1
                    break
                else:
                    print('输入错误，请重新输入！')
            except:
                print('输入错误，请重新输入！')

        # 获取所选课程章节
        studyCourse = lry.getCourseChapter(course_list[index])
        # print(studyCourse['video_list'])
        # print(studyCourse['question_list'])

        while True:
            print('--------------------------------------')
            type = eval(input("请选择功能[1:视频，2:答题]:\n"))
            if type == 1 or type == 2:
                break
            else:
                print('输入错误，请重新输入！')
        if type == 1:
            # 遍历课程章节进行学习
            for video in studyCourse['video_list']:
                lry.study(studyCourse['sesskey'], video)
        elif type == 2:
            idx = 0
            while idx < len(studyCourse['question_list']):
                try:
                    print('--------------------------------------')
                    print(studyCourse['question_list'][idx])
                    isG = input("[回车开始测验] (输入q跳过该节测验) 或 (输入做索引跳到指定测验):")
                    if isG == 'q':
                        idx = idx + 1
                        continue
                    elif isG == '':
                        lry.auto_answer(studyCourse['sesskey'], studyCourse['question_list'][idx][1][1])
                        idx = idx + 1
                    elif int(isG) > 0 and int(isG) <= len(studyCourse['question_list']):
                        idx = int(isG) - 1
                    else:
                        print("不存在该测验，请重新输入:")
                except:
                    print("非法输入！")
                    break
    input("结束使用:")