import sys
import argparse
import datetime
from operator import itemgetter

import requests.utils
from requests import HTTPError

version = '1.0'
https = 'https://github.com'
api_https = 'https://api.github.com'


# Проверка даты на валидность.
def valid_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        msg = "Не правильный формат даты: '{0}'".format(s) + ", должен соответствовать YYYY-MM-DD"
        raise argparse.ArgumentTypeError(msg)


# Описание команд.
def create_parser():
    pars = argparse.ArgumentParser(
        add_help=False,
        prog='github parser',
        description='''Эта программа проводит анализ репозитория github в указанной ветке, за указанный период времени
            используя REST API GitHub. В результатах анализа отображаются 30 самых активных участников
            по количеству коммитов, количество открытых, закрытых, "старых" pull request и issue.
            "Старым" считается pull request, если он не закрывается в течение 30 дней и до сих пор открыт.
            "Старым" считается issue, если он не закрывается в течение 14 дней и до сих пор открыт.''',
        epilog='''(c) November 2020. Автор программы, как всегда,
            не несёт никакой ответственности ни за что :)'''
    )
    pars.add_argument('-u', '--url',
                      help='''URL ОБЯЗАТЕЛЬНЫЙ ПАРАМЕТР, должен содержать полный путь до репозитория -
                        формат https://github.com/python/cpython
                        или https://api.github.com/repos/python/cpython''')
    pars.add_argument('-b', '--branche', default='master',
                      help='Название ветки репозитория, если не указана, то по умолчанию master.')
    pars.add_argument('-s', "--startdate", help="Дата начала - формат YYYY-MM-DD, если не указана, то неограничено.",
                      type=valid_date)
    pars.add_argument('-e', "--enddate", help="Дата конца - формат YYYY-MM-DD, если не указана, то неограничено.",
                      type=valid_date)
    pars.add_argument('--help', '-h', action='help', help='Справка.')
    pars.add_argument('-v', '--version', action='version', help='Вывести номер версии.',
                      version='%(prog)s {}'.format(version))
    return pars


# Проверка ссылок на работоспособность.
def check_response(u):
    try:
        respons = requests.get(u)
        # Если ответ успешен, исключения задействованы не будут.
        respons.raise_for_status()
        return respons
    except HTTPError as http_err:
        sys.stdout.write(f'HTTP error occurred: {http_err} \n')
        sys.exit()
    except Exception as err:
        sys.stdout.write(f'Other error occurred: {err} \n')
        sys.exit()


# Поиск количества страниц в запросе.
def parsing_paginate(respons):
    try:
        paginate = requests.utils.parse_header_links(respons.headers['link'].rstrip('>').replace('>,<', ',<'))
        page_paginate = paginate[1]['url']
        index = page_paginate.find("&page=")
        page_paginate = page_paginate[index + 6:]
        return page_paginate
    except KeyError:
        page_paginate = 1
        return page_paginate


# Поиск коммитов с их авторами.
def search_commits(respons, count_commit):
    index = 0
    while index < len(respons.json()):
        # Если author = None то пропускаем.
        try:
            login = respons.json()[index]['author']['login']
        except TypeError:
            login = None

        if login is not None:
            if login in count_commit:
                commit = count_commit[login]
                commit += 1
                count_commit[login] = commit
            else:
                count_commit[login] = 1
        index += 1

    return count_commit


# Поиск закрытых, открытых и "старых" pull request & issue.
def sum_rp(u, repo, sdate, edate, b, state):
    if b is not None:
        u = (u + repo + '+base:' + b + '+state:' + state + '+created:')
    else:
        u = (u + repo + '+state:' + state + '+created:')

    if sdate is not None and edate is not None:
        u = u + (str(sdate) + '..' + str(edate))

    elif sdate is not None:
        u = u + '>' + (str(sdate))
    elif edate is not None:
        u = u + '<' + (str(edate))

    respons = check_response(u)
    total_count = respons.json()['total_count']

    return total_count


# Поиск даты для старых коммитов
def search_old(day, d):
    d = d - datetime.timedelta(day)

    old = None
    edate = None

    if namespace.startdate is None and namespace.enddate is None:
        edate = d
    elif namespace.startdate is None and namespace.enddate is not None:
        if d > namespace.enddate:
            edate = namespace.enddate
        if d < namespace.enddate:
            edate = d
    elif namespace.startdate is not None and namespace.enddate is None:
        if d > namespace.startdate:
            edate = d
        else:
            old = 0
    elif namespace.startdate is not None and namespace.enddate is not None:
        if d > namespace.enddate:
            edate = namespace.enddate
        if namespace.enddate > d > namespace.startdate:
            edate = d

    if edate is None:
        edate = namespace.enddate

    return edate, old


if __name__ == '__main__':
    parser = create_parser()
    namespace = parser.parse_args(sys.argv[1:])

    date = datetime.date.today()
    # Если конечная дата > или = сегодняшнему дню, то присваиваем неограниченно.
    if namespace.enddate is not None:
        if date <= namespace.enddate:
            namespace.enddate = None

    # Если не введён url то выходит справка о программе.
    if namespace.url is None:
        parser.print_help()
        sys.exit()

    # Проверка дат (дата начала не должна быть больше даты окончания).
    if namespace.startdate is not None and namespace.enddate is not None:
        if namespace.startdate > namespace.enddate:
            sys.stdout.write("Дата начала не должна быть больше даты окончания \n")
            sys.exit()

    # Проверка доменного имени.
    if https in namespace.url or api_https in namespace.url:
        # Меняем https://github.com на https://api.github.com .
        if https in namespace.url:
            namespace.url = namespace.url[19:]
            url = 'https://api.github.com/repos/' + namespace.url + '/commits?sha=' + namespace.branche + '&per_page' \
                                                                                                          '=100 '
        else:
            url = namespace.url + '/commits?sha=' + namespace.branche + '&per_page=100'
        #  Если была указана дата начала поиска добавляем ключ
        if namespace.startdate is not None:
            url = url + '&since=' + str(namespace.startdate)
        #  Если была указана дата окончания поиска добавляем ключ.
        if namespace.enddate is not None:
            url = url + '&until=' + str(namespace.enddate)
        # Запоминаем имя репозитория.
        repository = url[url.find('repos/') + 6:url.find('/commits')]
        # Проверяем ссылку.
        response = check_response(url + '&page=1')
    else:
        sys.stdout.write('Эта ссылка "' + namespace.url + '" не имеет отношение к github \n')
        sys.exit()

    # Поиск количества страниц в запросе.
    pages = parsing_paginate(response)
    """ Проверка ограничения github на 60 запросов в час, для не зарегистрированных пользователей.
    Дополнительно можно записывать количество уже отправленных запросов , для вывода сообщения о превышении лимита.
    Но в задании про это не говорилось."""
    if int(pages) > 54:
        sys.stdout.write('Запрос превышает ограничение на количество обращений к серверу в час (не более 60) \n')
        sys.exit()
    # Массив для подсчета коммитов.
    user_commits = dict()
    # Поиск коммитов на странице.
    user_commits = search_commits(response, user_commits)

    # Начинаем со второй страницы, потому что первую уже проверили при тесте ссылки.
    page = 2
    while page <= int(pages):
        response = check_response(url + '&page=' + str(page))
        user_commits = search_commits(response, user_commits)
        page += 1

    sys.stdout.write('\n Поиск осуществляется в ветки - ' + namespace.branche + ' репозитория ' + repository + '\n\n')

    # Вывод таблицы с результатами пользователей и их коммитов.
    sys.stdout.write("{:<5} {:<25} {:<15}\n".format('№', 'Login', 'commits'))
    sys.stdout.write("-----------------------------------\n")
    i = 1

    for k, v in sorted(user_commits.items(), key=itemgetter(1), reverse=True)[:30]:
        sys.stdout.write("{:<5} {:<25} {:<15}\n".format(i, k, v))
        i += 1

    sys.stdout.write('\n PULL REQUEST: \n')

    # Поиск закрытых pull request.
    close_pr = sum_rp('https://api.github.com/search/issues?q=is:pr+repo:', repository,
                      namespace.startdate,
                      namespace.enddate, namespace.branche, 'closed')

    sys.stdout.write('Закрыто : ' + str(close_pr) + '\n')

    # Поиск открытых pull request.
    open_pr = sum_rp('https://api.github.com/search/issues?q=is:pr+repo:', repository, namespace.startdate,
                     namespace.enddate, namespace.branche, 'open')

    sys.stdout.write('Открыто : ' + str(open_pr) + '\n')

    # Поиск "старых" pull request.
    enddate, old_pr = search_old(30, date)

    if old_pr == 0:
        sys.stdout.write('Старые : ' + str(old_pr) + '\n')
    elif namespace.enddate is not None:
        if date > namespace.enddate:
            sys.stdout.write('Старые : ' + str(open_pr) + '\n')
    else:
        old_pr = sum_rp('https://api.github.com/search/issues?q=is:pr+repo:', repository, namespace.startdate,
                        enddate, namespace.branche, 'open')
        sys.stdout.write('Старые : ' + str(old_pr) + '\n')

    # Поиск закрытых issue.
    close_issue = sum_rp('https://api.github.com/search/issues?q=is:issue+repo:', repository,
                         namespace.startdate,
                         namespace.enddate, None, 'closed')

    sys.stdout.write('\n ISUES: \n')

    sys.stdout.write('Закрыто : ' + str(close_issue) + '\n')

    # Поиск открытых issue.
    open_issue = sum_rp('https://api.github.com/search/issues?q=is:issue+repo:', repository,
                        namespace.startdate,
                        namespace.enddate, None, 'open')

    sys.stdout.write('Открыто : ' + str(open_issue) + '\n')

    # Поиск "старых" issue.
    enddate, old_issue = search_old(14, date)

    if old_issue == 0:
        sys.stdout.write('Старые : ' + str(old_issue) + '\n')
    elif namespace.enddate is not None:
        if date > namespace.enddate:
            sys.stdout.write('Старые : ' + str(open_issue) + '\n')
    else:
        old_issue = sum_rp('https://api.github.com/search/issues?q=is:issue+repo:', repository,
                           namespace.startdate,
                           enddate, None, 'open')
        sys.stdout.write('Старые : ' + str(old_issue) + '\n')
