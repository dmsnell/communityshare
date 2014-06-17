(function() {
  'use strict';

  var module = angular.module(
    'communityshare.controllers.share',
    [
      'communityshare.services.share',
      'communityshare.services.conversation'
    ]);

  module.controller(
    'ShareController',
    function(Session, $scope, $routeParams, Share) {
      $scope.Session = Session;
      var shareId = $routeParams.shareId;
      var errorMessage = '';
      if (shareId !== undefined) {
        var sharePromise = Share.get(shareId);
        sharePromise.then(
          function(share) {
            $scope.share = share;
          },
          function(message) {
            var msg = 'Failed to load share';
            if (message) {
              msg += ': ' + message;
            }
            $scope.errorMessage = msg;
          });
      }
    });
      

  module.controller(
    'EditShareController',
    function($scope, share, $modalInstance, $q) {
      $scope.share = share;
      $scope.events = share.events;
      $scope.cancel = $modalInstance.close;
      var showErrorMessage = function(message) {
        var msg = 'Failed to save share details';
        if (message) {
          msg += ': ' + message;
        }
        $scope.errorMessage = msg;
      }
      var close = function() {
        $modalInstance.close($scope.share);
      };
      $scope.save = function() {
        for (var i=0; i<$scope.share.events.length; i++) {
          $scope.share.events[i].updateDateTimes();
        }
        var sharePromise = $scope.share.save();
        sharePromise.then(
          close,
          showErrorMessage);
      };
    });

  module.controller(
    'UpcomingEventsController',
    function($scope, Session, Evnt) {
      $scope.Session = Session;
      var now = new Date();
      var searchParams = {
        'datetime_start.greaterthan': now
      };
      var upcomingEventsPromise = Evnt.get_many(searchParams);
      $scope.infoMessage = 'Loading for upcoming events...';
      $scope.errorMessage = '';
      upcomingEventsPromise.then(
        function(events) {
          $scope.events = events;
          $scope.infoMessage = '';
          $scope.errorMessage = '';
        },
        function(message) {
          $scope.events = [];
          $scope.infoMessage = '';
          var msg = 'Failed to load upcoming events';
          if (message) {
            msg += ': ' + message;
          }
          $scope.errorMessage = msg;
        });
    });

  module.controller(
    'EventController',
    function($scope, Session, evnt, Question, Answer) {
      $scope.Session = Session;
      $scope.evnt = evnt;
      $scope.questions = [];
      var questionsPromise = Question.get_many_with_answers(
        Session.activeUser.id,
        {question_type: 'post_event'}
      );
      questionsPromise.then(
        function(questions) {
          $scope.questions = [];
          // We only show the unanswered questions.
          for (var i=0; i<questions.length; i++) {
            var question = questions[i];
            if (!question.answer.text) {
              $scope.questions.push(question);
            }
          }
        });
      $scope.questions = [];
      $scope.save = function() {
        var allPromises = [];
        var saveAnswerPromises = [];
        for (var i=0; i<$scope.questions.length; i++) {
          var question = $scope.questions[i];
          var answer = question.answer;
          if (answer.text) {
            var saveAnswerPromise = answer.save();
            saveAnswerPromise.then(
              function() {
                var index = $scope.questions.indexOf(question);
                $scope.questions.splice(index, 1);
              }
            );
            saveAnswerPromises.push(saveAnswerPromise);
            allPromises.push(saveAnswerPromise);
          }
        }
      };
    });
  
})();
