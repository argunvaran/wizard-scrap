
import os
import sys
import logging
from django.core.management.base import BaseCommand
from django.conf import settings

# Ensure scraper module is reachable
sys.path.append(os.path.abspath(os.path.join(settings.BASE_DIR, '..')))

from scraper.bilyoner import BilyonerScraper
from data_manager.models import BilyonerBulletinStaging

logger = logging.getLogger('scraper')

class Command(BaseCommand):
    help = 'Scrapes Bilyoner betting bulletin and updates the staging database'

    def handle(self, *args, **options):
        logger.info("COMMAND START: update_bilyoner_bulletin")
        self.stdout.write(self.style.WARNING("Starting Bilyoner Scrape... Only fetching Turkey, England, Spain, Italy."))
        
        # Initialize Scraper
        scraper = BilyonerScraper()
        
        try:
            # Run Scrape
            matches = scraper.scrape()
            
            if not matches:
                msg = "No matches found!"
                self.stdout.write(self.style.ERROR(msg))
                logger.warning(msg)
                return

            msg = f"Found {len(matches)} matches. Updating STAGING database..."
            self.stdout.write(self.style.SUCCESS(msg))
            logger.info(msg)
            
            # Clear Staging Table
            BilyonerBulletinStaging.objects.all().delete()
            
            count = 0
            for m in matches:
                # Direct Create since we cleared (scraped list is unique by key)
                BilyonerBulletinStaging.objects.create(
                    unique_key=m['unique_key'],
                    country=m.get('country', 'TURKEY'),
                    league=m.get('league', '-'),
                    match_date=m.get('match_date', ''),
                    match_time=m.get('match_time', '00:00'),
                    home_team=m.get('home_team', 'Unknown'),
                    away_team=m.get('away_team', 'Unknown'),
                    ms_1=m.get('ms_1', '-'),
                    ms_x=m.get('ms_x', '-'),
                    ms_2=m.get('ms_2', '-'),
                    under_2_5=m.get('under_2_5', '-'),
                    over_2_5=m.get('over_2_5', '-')
                )
                count += 1

            done_msg = f"Done. Saved {count} matches to Staging Area."
            self.stdout.write(self.style.SUCCESS(done_msg))
            logger.info(done_msg)
            self.stdout.write(self.style.WARNING("Please review the data at: /scrape-review/ before publishing."))

        except Exception as e:
            err_msg = f"Error during execution: {e}"
            self.stdout.write(self.style.ERROR(err_msg))
            logger.error(err_msg, exc_info=True)
