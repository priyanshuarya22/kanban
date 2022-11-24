import json

from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request, redirect, make_response
from datetime import datetime
import matplotlib.pyplot as plt
from flask_restful import Api, fields, reqparse, Resource, marshal_with
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite'
db = SQLAlchemy()
db.init_app(app)
api = Api(app)
app.app_context().push()

output_field_list = {
    "id": fields.Integer,
    "name": fields.String,
    "description": fields.String,
    "user": fields.Integer
}

output_field_task = {
    "id": fields.Integer,
    "title": fields.String,
    "content": fields.String,
    "deadline": fields.String,
    "creation": fields.String,
    "done": fields.Boolean,
    "list": fields.Integer,
    "modified": fields.String,
    "completedOn": fields.String
}


class NotFoundError(HTTPException):
    def __init__(self):
        self.response = make_response('', 404)


class GeneralError(HTTPException):
    def __init__(self, error_code, error_message):
        message = {
            "error_code": error_code,
            "error_message": error_message
        }
        self.response = make_response(json.dumps(message), 400)


class AlreadyExist(HTTPException):
    def __init__(self):
        self.response = make_response('', 409)


list_parser = reqparse.RequestParser()
list_parser.add_argument('name')
list_parser.add_argument('description')
list_parser.add_argument('user')

task_parser = reqparse.RequestParser()
task_parser.add_argument('title')
task_parser.add_argument('content')
task_parser.add_argument('deadline')
task_parser.add_argument('done')
task_parser.add_argument('list')


class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    username = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    lists = db.relationship("Users", secondary='lists')


class Lists(db.Model):
    __tablename__ = 'lists'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String)
    user = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tasks = db.relationship('Lists', secondary='tasks')


class Tasks(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    title = db.Column(db.String, nullable=False)
    content = db.Column(db.String)
    deadline = db.Column(db.String, nullable=False)
    creation = db.Column(db.String, nullable=False)
    done = db.Column(db.Boolean, nullable=False)
    modified = db.Column(db.String)
    completedOn = db.Column(db.String)
    list = db.Column(db.Integer, db.ForeignKey('lists.id'), nullable=False)


@app.route('/', methods=['GET'])
def index():
    return render_template("index.html")


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    global userName, userId
    if request.method == 'GET':
        return render_template("signup.html")
    if request.method == 'POST':
        username = request.form["username"]
        password = request.form["password"]
        name = request.form["name"]
        check = Users.query.filter_by(username=username).first()
        if check is not None:
            return render_template("signup.html", exist=True)
        user = Users(username=username, password=password, name=name)
        db.session.add(user)
        db.session.commit()
        userName = name
        userId = user.id
        return render_template("board.html", name=name)


@app.route('/login', methods=['POST'])
def login():
    global userName, userId
    username = request.form["username"]
    password = request.form["password"]
    user = Users.query.filter_by(username=username, password=password).first()
    if user is None:
        return render_template("index.html", exist=True)
    userName = user.name
    userId = user.id
    return redirect('/board')


@app.route('/board', methods=['GET'])
def board():
    global userName, userId
    lists = Lists.query.filter_by(user=userId).all()
    list_list = []
    for list_ in lists:
        tasks = Tasks.query.filter_by(list=list_.id).all()
        late = []
        for task in tasks:
            if task.done == 0 and task.deadline < str(datetime.now())[:10]:
                late.append(task.id)
        list_dict = {'id': list_.id, 'name': list_.name, 'tasks': tasks, 'late': late}
        list_list.append(list_dict)
    return render_template("board.html", name=userName, lists=list_list)


@app.route('/create_list', methods=['GET', 'POST'])
def create_list():
    global userName, userId
    if request.method == 'GET':
        return render_template('create_list.html', name=userName)
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        check = Lists.query.filter_by(name=name, user=userId).first()
        if check is not None:
            return render_template('create_list.html', exist=True)
        list_ = Lists(name=name, description=description, user=userId)
        db.session.add(list_)
        db.session.commit()
        return redirect('/board')


@app.route('/logout', methods=['GET'])
def logout():
    global userName, userId
    userName = ''
    userId = ''
    return redirect('/')


@app.route('/edit_list/<int:list_id>', methods=['GET', 'POST'])
def edit_list(list_id):
    global userName
    list_ = Lists.query.filter_by(id=list_id).first()
    if request.method == 'GET':
        return render_template('edit_list.html', list=list_, name=userName)
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        if name != list_.name:
            check = Lists.query.filter_by(name=name, user=list_.user).first()
            if check is not None:
                return render_template('edit_list.html', list=list_, name=userName, exist=True)
        list_.name = name
        list_.description = description
        db.session.commit()
        return redirect('/board')


@app.route('/delete_list/<int:list_id>', methods=['GET'])
def delete_list(list_id):
    list_ = Lists.query.filter_by(id=list_id).first()
    tasks = Tasks.query.filter_by(list=list_.id).all()
    for task in tasks:
        db.session.delete(task)
    db.session.delete(list_)
    db.session.commit()
    return redirect('/board')


@app.route('/create_task/<int:list_id>', methods=['GET', 'POST'])
def create_task(list_id):
    global userName
    defaultList = Lists.query.filter_by(id=list_id).first()
    lists = Lists.query.filter().all()
    lists.remove(defaultList)
    if request.method == 'GET':
        return render_template('create_task.html', name=userName, defaultList=defaultList, lists=lists)
    if request.method == 'POST':
        listId = request.form['listId']
        title = request.form['title']
        content = request.form['content']
        deadline = request.form['deadline']
        flag = False
        try:
            done = request.form['done']
            flag = True
        except Exception:
            pass
        creation = str(datetime.now())[:10]
        check = Tasks.query.filter_by(title=title, list=listId).first()
        if check is not None:
            return render_template('create_task.html', name=userName, defaultList=defaultList, lists=lists, exist=True)
        task = Tasks(title=title, content=content, deadline=deadline, done=flag, list=listId, creation=creation)
        db.session.add(task)
        db.session.commit()
        return redirect('/board')


@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    global userName
    task = Tasks.query.filter_by(id=task_id).first()
    defaultList = Lists.query.filter_by(id=task.list).first()
    lists = Lists.query.filter().all()
    lists.remove(defaultList)
    if request.method == 'GET':
        return render_template('edit_task.html', name=userName, defaultList=defaultList, lists=lists, task=task)
    if request.method == 'POST':
        listId = request.form['listId']
        title = request.form['title']
        content = request.form['content']
        deadline = request.form['deadline']
        if title != task.title:
            check = Tasks.query.filter_by(title=title, list=listId).first()
            if check is not None:
                return render_template('edit_task.html', name=userName, defaultList=defaultList, lists=lists, task=task,
                                       exist=True)
        try:
            done = request.form['done']
            task.done = True
            task.completedOn = str(datetime.now())[:10]
        except:
            task.done = False
            task.completedOn = None
        task.list = listId
        task.title = title
        task.content = content
        task.deadline = deadline
        task.modified = str(datetime.now())[:10]
        db.session.commit()
        return redirect('/board')


@app.route('/delete_task/<int:task_id>', methods=['GET'])
def delete_task(task_id):
    task = Tasks.query.filter_by(id=task_id).first()
    db.session.delete(task)
    db.session.commit()
    return redirect('/board')


@app.route('/summary', methods=['GET'])
def summary():
    global userName, userId
    lists = Lists.query.filter_by(user=userId).all()
    list_list = []
    for list_ in lists:
        tasks = Tasks.query.filter_by(list=list_.id).all()
        dateWiseCount = {}
        completed = 0
        late = 0
        for task in tasks:
            creation = task.creation[:10]
            dateWiseCount[creation] = dateWiseCount.get(creation, 0) + 1
            if task.done == 0 and task.deadline < str(datetime.now())[:10]:
                late += 1
            else:
                completed += 1
        total = completed + late
        list_dict = {'id': list_.id, 'name': list_.name, 'completed': completed, 'passed': late, 'total': total}
        list_list.append(list_dict)
        dates = list(dateWiseCount.keys())
        count = list(dateWiseCount.values())
        plt.bar(dates, count)
        plt.xlabel("Dates")
        plt.ylabel("No. of tasks created")
        plt.title("Tasks created on different dates")
        plt.savefig('static/' + str(userId) + '_' + str(list_.id))
        plt.close()
    return render_template('summary.html', name=userName, lists=list_list, userId=userId)


class ListAPI(Resource):
    @marshal_with(output_field_list)
    def get(self, list_id):
        list_ = Lists.query.filter_by(id=list_id).first()
        if list_ is not None:
            return list_
        else:
            raise NotFoundError()

    @marshal_with(output_field_list)
    def put(self, list_id):
        args = list_parser.parse_args()
        name = args.get('name', None)
        description = args.get('description', None)
        user = args.get('user', None)
        if name is None:
            raise GeneralError(error_code='LIST001', error_message="Name is required")
        if user is None:
            raise GeneralError(error_code='LIST002', error_message='User is required')
        user = int(user)
        user_ = Users.query.filter_by(id=user).first()
        if user_ is None:
            raise GeneralError(error_code='LIST003', error_message='User does not exist')
        list_ = Lists.query.filter_by(id=list_id).first()
        if name != list_.name:
            check = Lists.query.filter_by(name=name, user=user).first()
            if check is not None:
                raise AlreadyExist()
        list_.name = name
        list_.description = description
        list_.user = user
        db.session.commit()
        return list_

    def delete(self, list_id):
        list_ = Lists.query.filter_by(id=list_id).first()
        if list_ is None:
            raise NotFoundError()
        tasks = Tasks.query.filter_by(list=list_id).all()
        for task in tasks:
            db.session.delete(task)
        db.session.delete(list_)
        db.session.commit()

    @marshal_with(output_field_list)
    def post(self):
        args = list_parser.parse_args()
        name = args.get('name', None)
        description = args.get('description', None)
        user = args.get('user', None)
        if name is None:
            raise GeneralError(error_code='LIST001', error_message="Name is required")
        if user is None:
            raise GeneralError(error_code='LIST002', error_message='User is required')
        user = int(user)
        user_ = Users.query.filter_by(id=user).first()
        if user_ is None:
            raise GeneralError(error_code='LIST003', error_message='User does not exist')
        check = Lists.query.filter_by(name=name, user=user).first()
        if check is not None:
            raise AlreadyExist()
        list_ = Lists(name=name, description=description, user=user)
        db.session.add(list_)
        db.session.commit()
        return list_, 201


class TaskAPI(Resource):
    @marshal_with(output_field_task)
    def get(self, task_id):
        task = Tasks.query.filter_by(id=task_id).first()
        if task is not None:
            return task
        raise NotFoundError()

    @marshal_with(output_field_task)
    def put(self, task_id):
        args = task_parser.parse_args()
        title = args.get('title', None)
        content = args.get('content', None)
        deadline = args.get('deadline', None)
        done = args.get('done', None)
        list_id = args.get('list', None)
        if title is None:
            raise GeneralError(error_code='TASK001', error_message='Title is required')
        if deadline is None:
            raise GeneralError(error_code='TASK002', error_message='Deadline is required')
        if done is None:
            raise GeneralError(error_code='TASK003', error_message='Done is required')
        if list_id is None:
            raise GeneralError(error_code='TASK004', error_message='List is required')
        flag = False
        if done == 'True':
            flag = True
        list_id = int(list_id)
        list_ = Lists.query.filter_by(id=list_id).first()
        if list_ is None:
            raise GeneralError(error_code='TASK005', error_message='List does not exist')
        task = Tasks.query.filter_by(id=task_id).first()
        if title != task.title:
            check = Tasks.query.filter_by(title=title, list=list_id).first()
            if check is not None:
                raise AlreadyExist()
        task.list = list_id
        task.title = title
        task.content = content
        task.deadline = deadline
        task.modified = str(datetime.now())[:10]
        task.done = flag
        if flag:
            task.completedOn = str(datetime.now())[:10]
        else:
            task.completedOn = None
        db.session.commit()
        return task

    def delete(self, task_id):
        task = Tasks.query.filter_by(id=task_id).first()
        if task is None:
            raise NotFoundError()
        db.session.delete(task)
        db.session.commit()

    @marshal_with(output_field_task)
    def post(self):
        args = task_parser.parse_args()
        title = args.get('title', None)
        content = args.get('content', None)
        deadline = args.get('deadline', None)
        done = args.get('done', None)
        list_id = args.get('list', None)
        if title is None:
            raise GeneralError(error_code='TASK001', error_message='Title is required')
        if deadline is None:
            raise GeneralError(error_code='TASK002', error_message='Deadline is required')
        if done is None:
            raise GeneralError(error_code='TASK003', error_message='Done is required')
        if list_id is None:
            raise GeneralError(error_code='TASK004', error_message='List is required')
        flag = False
        if bool == 'True':
            flag = True
        list_id = int(list_id)
        list_ = Lists.query.filter_by(id=list_id).first()
        if list_ is None:
            raise GeneralError(error_code='TASK005', error_message='List does not exist')
        check = Tasks.query.filter_by(id=list_id).first()
        if check is not None:
            raise AlreadyExist()
        creation = str(datetime.now())[:10]
        task = Tasks(title=title, content=content, deadline=deadline, done=flag, list=list_id,
                     creation=creation)
        db.session.add(task)
        db.session.commit()
        return task, 201


api.add_resource(ListAPI, "/api/list", "/api/list/<int:list_id>")
api.add_resource(TaskAPI, '/api/task', '/api/task/<int:task_id>')

userName = ''
userId = ''
if __name__ == '__main__':
    app.run()
