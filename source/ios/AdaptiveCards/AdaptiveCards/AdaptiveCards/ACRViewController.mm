//
//  ACRViewController.m
//  ACRViewController
//
//  Copyright © 2017 Microsoft. All rights reserved.
//

#import "ACRViewController.h"
#import "ACOHostConfigPrivate.h"
#import "ACOAdaptiveCardPrivate.h"
#import "SharedAdaptiveCard.h"
#import "ACRRendererPrivate.h"
#import <AVFoundation/AVFoundation.h>
#import "Container.h"
#import "ColumnSet.h"
#import "Column.h"
#import "Image.h"
#import "ACRImageRenderer.h"

using namespace AdaptiveCards;

@implementation ACRViewController
{
    std::shared_ptr<AdaptiveCard> _adaptiveCard;
    std::shared_ptr<HostConfig> _hostConfig;
    CGRect _guideFrame;
    NSMutableDictionary *_imageViewMap;
    dispatch_queue_t _serial_queue;
}

- (instancetype)initWithNibName:(NSString *)nibNameOrNil bundle:(NSBundle *)nibBundleOrNil
{
    self = [super initWithNibName:nibNameOrNil bundle:nibBundleOrNil];
    if(self){
        _guideFrame = CGRectMake(0, 0, 0, 0);
        _hostConfig = std::make_shared<HostConfig>();
        _imageViewMap = [[NSMutableDictionary alloc] init];
        _serial_queue = dispatch_queue_create("io.adaptiveCards.serial_queue", DISPATCH_QUEUE_SERIAL);
    }
    return self;
}

// Initializes ACRViewController instance with HostConfig and AdaptiveCard
- (instancetype)init:(ACOAdaptiveCard *)card
          hostconfig:(ACOHostConfig *)config
               frame:(CGRect)frame
{
    self = [self initWithNibName:nil bundle:nil];
    if(self)
    {
        _adaptiveCard = [card getCard];
        if(config)
        {
            _hostConfig = [config getHostConfig];
        }
        _guideFrame = frame;
        _imageViewMap = [[NSMutableDictionary alloc] init];
        _serial_queue = dispatch_queue_create("io.adaptiveCards.serial_queue", NULL);
    }
    return self;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    [self render];
}

- (void)render
{
    UIView *view = self.view;
    view.frame = _guideFrame;
    NSMutableArray *inputs = [[NSMutableArray alloc] init];

    std::string backgroundImage = _adaptiveCard->GetBackgroundImage();
    NSString* imgUrl = nil;
    if(!backgroundImage.empty())
        imgUrl = [[NSString alloc] initWithCString:backgroundImage.c_str() encoding:NSUTF8StringEncoding];
    if (imgUrl)
    {
        NSURL *url = [NSURL URLWithString:imgUrl];
        UIImage *img = [UIImage imageWithData:[NSData dataWithContentsOfURL:url]];
        UIImageView *imgView = [[UIImageView alloc] initWithImage:img];
        [view addSubview:imgView];
        [view sendSubviewToBack:imgView];
        [NSLayoutConstraint activateConstraints:
         @[[imgView.trailingAnchor constraintEqualToAnchor:view.trailingAnchor],
           [imgView.topAnchor constraintEqualToAnchor:view.topAnchor],
           [imgView.trailingAnchor constraintEqualToAnchor:view.trailingAnchor],
           ]];
    }
    ContainerStyle style = (_hostConfig->adaptiveCard.allowCustomStyle)? _adaptiveCard->GetStyle() : _hostConfig->actions.showCard.style;
    if(style != ContainerStyle::None)
    {
        unsigned long num = 0;
        if(style == ContainerStyle::Emphasis)
        {
            num = std::stoul(_hostConfig->containerStyles.emphasisPalette.backgroundColor.substr(1), nullptr, 16);
        }
        else
        {
            num = std::stoul(_hostConfig->containerStyles.defaultPalette.backgroundColor.substr(1), nullptr, 16);
        }
        view.backgroundColor =
        [UIColor colorWithRed:((num & 0x00FF0000) >> 16) / 255.0
                        green:((num & 0x0000FF00) >>  8) / 255.0
                         blue:((num & 0x000000FF)) / 255.0
                        alpha:((num & 0xFF000000) >> 24) / 255.0];
    }
    std::vector<std::shared_ptr<BaseCardElement>> body = _adaptiveCard->GetBody();
    if(!body.empty())
    {
        int serialNumber = 0;
        [self addImageBlockToConcurrentQueue:body serialNumber:serialNumber];
    }

    UIView *newView = [ACRRenderer renderWithAdaptiveCards:_adaptiveCard
                                                             inputs:inputs
                                                     viewController:self
                                                         guideFrame:_guideFrame
                                                         hostconfig:_hostConfig];
    // new rendered adaptiveCard view is added as a sub view
    [view addSubview:newView];
    // affix the left margin of the rendered adaptiveCard to current view
    NSLayoutConstraint *constraint =
    [NSLayoutConstraint constraintWithItem:view
                                 attribute:NSLayoutAttributeLeading
                                 relatedBy:NSLayoutRelationEqual
                                    toItem:newView
                                 attribute:NSLayoutAttributeLeading
                                multiplier:1.0
                                  constant:0];
    [view addConstraint:constraint];
    // affix the right margin of the rendered adaptiveCard to current view
    constraint =
    [NSLayoutConstraint constraintWithItem:view
                                 attribute:NSLayoutAttributeTrailing
                                 relatedBy:NSLayoutRelationEqual
                                    toItem:newView
                                 attribute:NSLayoutAttributeTrailing
                                multiplier:1.0
                                  constant:0];
    [view addConstraint:constraint];

    constraint =
    [NSLayoutConstraint constraintWithItem:view
                                 attribute:NSLayoutAttributeTop
                                 relatedBy:NSLayoutRelationLessThanOrEqual
                                    toItem:newView
                                 attribute:NSLayoutAttributeTop
                                multiplier:1.0
                                  constant:0];
    [view addConstraint:constraint];

    constraint =
    [NSLayoutConstraint constraintWithItem:view
                                 attribute:NSLayoutAttributeBottom
                                 relatedBy:NSLayoutRelationGreaterThanOrEqual
                                    toItem:newView
                                 attribute:NSLayoutAttributeBottom
                                multiplier:1.0
                                  constant:0];
    [view addConstraint:constraint];

    [NSLayoutConstraint activateConstraints:
     @[[newView.leadingAnchor constraintEqualToAnchor:view.leadingAnchor],
       [newView.topAnchor constraintEqualToAnchor:view.topAnchor]]];
}

// Walk through adaptive cards elements and if images are found, download and process images concurrently and on different thread
// from main thread, so images process won't block UI thread.
- (int) addImageBlockToConcurrentQueue:(std::vector<std::shared_ptr<BaseCardElement>> const &) body serialNumber:(int)serialNumber
{
    for(auto &elem : body)
    {
        switch (elem->GetElementType())
        {
            case CardElementType::Image:
            {
                /// dispatch to concurrent queue
                std::shared_ptr<Image> imgElem = std::dynamic_pointer_cast<Image>(elem);
                /// generate a string key to uniquely identify Image
                std::string serial_number_as_string = std::to_string(serialNumber);
                // Id field is optional, if empty, add new one
                if("" == imgElem->GetId())
                {
                    imgElem->SetId("_" + serial_number_as_string);
                }
                else
                {
                    // concat a newly generated key to a existing id, the key will be removed after use
                    imgElem->SetId(imgElem->GetId() + "_" + serial_number_as_string);
                }

                ++serialNumber;
                // run image downloading and processing on global queue which is concurrent and different from main queue
                dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0),
                    ^{
                         NSString *urlStr = [NSString stringWithCString:imgElem->GetUrl().c_str()
                                                               encoding:[NSString defaultCStringEncoding]];
                         NSURL *url = [NSURL URLWithString:urlStr];
                         // download image
                         UIImage *img = [UIImage imageWithData:[NSData dataWithContentsOfURL:url]];
                         CGSize cgsize = [ACRImageRenderer getImageSize:imgElem withHostConfig:_hostConfig];
                         // scale image
                         UIGraphicsBeginImageContext(cgsize);
                         [img drawInRect:(CGRectMake(0, 0, cgsize.width, cgsize.height))];
                         img = UIGraphicsGetImageFromCurrentImageContext();
                         UIGraphicsEndImageContext();
                         // UITask can't be run on global queue, add task to main queue
                         dispatch_async(dispatch_get_main_queue(),
                             ^{
                                  __block UIImageView *view = nil;
                                  // generate key for imageMap from image element's id
                                  NSString *key = [NSString stringWithCString:imgElem->GetId().c_str() encoding:[NSString defaultCStringEncoding]];
                                  // syncronize access to image map
                                  dispatch_sync(_serial_queue,
                                      ^{
                                           // UIImageView is not ready, cashe UIImage
                                           if(!_imageViewMap[key])
                                           {
                                               _imageViewMap[key] = img;
                                           }
                                           // UIImageView ready, get view
                                           else
                                           {
                                               view = _imageViewMap[key];
                                           }
                                      });

                                   // if view is available, set image to it, and continue image processing
                                  if(view)
                                  {
                                      view.image = img;
                                      view.contentMode = UIViewContentModeScaleAspectFit;
                                      view.clipsToBounds = NO;
                                      if(imgElem->GetImageStyle() == ImageStyle::Person)
                                      {
                                          CALayer *imgLayer = view.layer;
                                          [imgLayer setCornerRadius:cgsize.width/2];
                                          [imgLayer setMasksToBounds:YES];
                                      }
                                  }
                              });
                         }
                );
                break;
            }
            // continue on search
            case CardElementType::Container:
            {
                std::shared_ptr<Container> container = std::static_pointer_cast<Container>(elem);
                std::vector<std::shared_ptr<BaseCardElement>> &new_body = container->GetItems();
                // update serial number that is used for generating unique key for image_map
                serialNumber = [self addImageBlockToConcurrentQueue: new_body serialNumber:serialNumber];
                break;
            }
            // continue on search
            case CardElementType::Column:
            {
                std::shared_ptr<Column> colum = std::static_pointer_cast<Column>(elem);
                std::vector<std::shared_ptr<BaseCardElement>> &new_body = colum->GetItems();
                // update serial number that is used for generating unique key for image_map
                serialNumber = [self addImageBlockToConcurrentQueue: new_body serialNumber:serialNumber];
                break;
            }
            // continue on search
            case CardElementType::ColumnSet:
            {
                std::shared_ptr<ColumnSet> columSet = std::static_pointer_cast<ColumnSet>(elem);
                std::vector<std::shared_ptr<Column>> &columns = columSet->GetColumns();
                // ColumnSet is vector of Column, instead of vector of BaseCardElement
                for(auto &colum : columns)
                {
                    // update serial number that is used for generating unique key for image_map
                    serialNumber = [self addImageBlockToConcurrentQueue: colum->GetItems() serialNumber:serialNumber];
                }
                break;
            }
            default:
            {
                /// no work is needed
                break;
            }
        }
    }
    return serialNumber;
}

- (NSMutableDictionary *) getImageMap
{
    return _imageViewMap;
}
- (dispatch_queue_t) getSerialQueue
{
    return _serial_queue;
}

@end
