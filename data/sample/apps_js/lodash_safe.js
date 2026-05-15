// FALSE_POSITIVE example: app uses lodash but never invokes _.template()
const _ = require('lodash');
const express = require('express');
const app = express();

function summarizeUsers(users) {
    const result = _.map(users, u => _.capitalize(u.name));
    const grouped = _.groupBy(result, 'dept');
    return _.filter(_.values(grouped), g => g.length > 1);
}

function renderHome(req, res) {
    const summary = summarizeUsers(req.app.locals.users);
    res.json(summary);
}

app.get('/', renderHome);

module.exports = { summarizeUsers, renderHome };
