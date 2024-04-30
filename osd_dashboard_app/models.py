from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import datetime, timedelta
import requests


class GithubRepoManager(models.Manager):
    """Filter repositories that include 'hacktoberfest' in their topics."""
    def with_hacktoberfest(self):
        return self.get_queryset().filter(topics__contains=['hacktoberfest']).order_by('stargazers_count')
    def random_featured(self):
        return self.get_queryset().order_by('?').first()
# If performance becomes an issue, consider alternative methods to achieve randomness, such as selecting a random index in Python and retrieving the specific entry by ID.

class GithubUser(models.Model):
    username = models.CharField(max_length=100)
    avatar_url = models.URLField()
    profile_url = models.URLField()

    def __str__(self):
        return self.username

class GithubRepo(models.Model):
    name = models.CharField(max_length=255)
    license = models.CharField(max_length=100)
    topics = models.JSONField()
    url = models.URLField()
    avatar_url = models.URLField()
    commits_url = models.URLField()
    stargazers_count = models.IntegerField()
    latest_commit_timestamp = models.DateTimeField(default=timezone.now, null=True, blank=True)
    latest_committer = models.CharField(max_length=255, null=True, blank=True)
    
    objects = GithubRepoManager()
    
    def __str__(self):
        return self.name

# does views latest_contributors logic need to go here?
class RepoContributor(models.Model):
    name = models.CharField(max_length=255)
    repo = models.ForeignKey(GithubRepo, on_delete=models.CASCADE)
    commit_url = models.URLField()
    last_commit_repo_name = models.CharField(max_length=255)


class OSDUserProfile(AbstractUser):
    github_username = models.CharField(max_length=100, blank=True, null=True)
    donut_stampcard_count = models.IntegerField(default=0)
    donut_boxes = models.IntegerField(default=0)
    last_commit_date = models.DateTimeField(null=True, blank=True)
    last_commit_repo_name = models.CharField(max_length=255, null=True, blank=True)
